from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
import logging
from urllib.parse import quote
from typing import Any, Dict, Iterable, Optional

import httpx
import jwt

from .config import PanoramaGatewaySettings, get_panorama_settings

logger = logging.getLogger(__name__)


class PanoramaGatewayError(RuntimeError):
    """Raised when the Panorama gateway returns an error response."""

    def __init__(self, message: str, status_code: int, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _canonical_conversation_id(payload: Dict[str, Any]) -> str | None:
    user_id = payload.get("userId")
    conversation_id = payload.get("conversationId")
    if not isinstance(user_id, str) or not user_id:
        return None
    if not isinstance(conversation_id, str) or not conversation_id:
        return None
    return _encode_identifier({"userId": user_id, "conversationId": conversation_id})


def _normalize_entity_record(entity: str, payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    if entity == "conversations":
        canonical_id = _canonical_conversation_id(payload)
        if not canonical_id:
            logger.error(
                "Panorama contract mismatch entity=%s keys=%s payload=%s",
                entity,
                sorted(payload.keys()),
                PanoramaGatewayClient._truncate_payload(payload),
            )
            raise PanoramaGatewayError(
                "Gateway contract mismatch for conversations",
                502,
                payload,
            )
        return {
            **payload,
            "id": canonical_id,
        }

    return payload


def _normalize_entity_response(entity: str, payload: Any) -> Any:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return {
            **payload,
            "data": [_normalize_entity_record(entity, item) for item in payload["data"]],
        }
    if isinstance(payload, list):
        return [_normalize_entity_record(entity, item) for item in payload]
    return _normalize_entity_record(entity, payload)


def _encode_identifier(identifier: Any) -> str:
    """Coerce identifiers into the colon-delimited format expected by the gateway."""

    def _encode_part(part: Any) -> str:
        return quote(str(part), safe="")

    if isinstance(identifier, str):
        return identifier
    if isinstance(identifier, dict):
        return ":".join(_encode_part(value) for value in identifier.values())
    if isinstance(identifier, Iterable):
        parts: Iterable[str] = (_encode_part(part) for part in identifier)
        return ":".join(parts)
    raise ValueError(f"Unsupported identifier type: {type(identifier)}")


class PanoramaGatewayClient:
    """HTTP client wrapper for Panorama's data gateway."""

    def __init__(
        self,
        settings: PanoramaGatewaySettings | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or get_panorama_settings()
        self._client = client or httpx.Client(
            base_url=self._settings.base_url,
            timeout=self._settings.request_timeout,
        )

    def __enter__(self) -> "PanoramaGatewayClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ---- low-level helpers -------------------------------------------------
    def _build_token(self) -> str:
        now = int(time.time())
        payload: Dict[str, Any] = {
            "iat": now,
            "exp": now + 300,
            "service": self._settings.service_name,
            "roles": self._settings.roles,
            "tenant": self._settings.tenant_id,
        }
        if self._settings.jwt_audience:
            payload["aud"] = self._settings.jwt_audience
        if self._settings.jwt_issuer:
            payload["iss"] = self._settings.jwt_issuer

        return jwt.encode(payload, self._settings.jwt_secret, algorithm="HS256")

    def _default_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._build_token()}",
            "x-tenant-id": self._settings.tenant_id,
            "Accept": "application/json",
        }

    @staticmethod
    def _truncate_payload(payload: Any, limit: int = 512) -> Any:
        if payload is None:
            return None
        try:
            text = json.dumps(payload)
        except (TypeError, ValueError):
            text = str(payload)
        if len(text) <= limit:
            return payload
        return text[:limit] + "...<truncated>"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Dict[str, Any] | None = None,
        json_body: Any | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = self._default_headers()
        if method.upper() in {"POST", "PATCH", "PUT", "DELETE"}:
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Panorama %s %s params=%s body=%s",
                method,
                path,
                params,
                self._truncate_payload(json_body),
            )

        # map network/transient failures to gateway errors so callers can degrade gracefully
        try:
            response = self._client.request(
                method=method,
                url=path,
                headers=headers,
                params=params,
                json=json_body,
            )
        except httpx.TimeoutException as exc:
            logger.warning("Panorama timeout %s %s: %s", method, path, exc)
            raise PanoramaGatewayError("Gateway request timed out", 504, str(exc)) from exc
        except httpx.RequestError as exc:
            logger.warning("Panorama network error %s %s: %s", method, path, exc)
            raise PanoramaGatewayError("Gateway request failed", 503, str(exc)) from exc

        if response.status_code >= 400:
            message = f"Gateway request failed ({response.status_code})"
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            logger.warning(
                "Panorama error %s %s status=%s payload=%s",
                method,
                path,
                response.status_code,
                payload,
            )
            raise PanoramaGatewayError(message, response.status_code, payload)

        if response.status_code == 204:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Panorama %s %s status=204 no-content", method, path)
            return None

        if response.headers.get("content-type", "").startswith("application/json"):
            body = response.json()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Panorama %s %s status=%s body=%s",
                    method,
                    path,
                    response.status_code,
                    self._truncate_payload(body),
                )
            return body

        text = response.text
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Panorama %s %s status=%s body=%s",
                method,
                path,
                response.status_code,
                text[:512] + ("...<truncated>" if len(text) > 512 else ""),
            )
        return text

    # ---- CRUD facades ------------------------------------------------------
    def list(self, entity: str, query: Dict[str, Any] | None = None) -> Dict[str, Any]:
        params = None
        if query:
            params = {}
            for key, value in query.items():
                if isinstance(value, (dict, list)):
                    params[key] = json.dumps(value)
                else:
                    params[key] = value
        response = self._request("GET", f"/v1/{entity}", params=params)
        return _normalize_entity_response(entity, response)

    def get(self, entity: str, identifier: Any) -> Any:
        encoded_id = _encode_identifier(identifier)
        response = self._request("GET", f"/v1/{entity}/{encoded_id}")
        return _normalize_entity_response(entity, response)

    def create(
        self,
        entity: str,
        payload: Dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        response = self._request(
            "POST",
            f"/v1/{entity}",
            json_body=payload,
            idempotency_key=idempotency_key,
        )
        return _normalize_entity_response(entity, response)

    def update(
        self,
        entity: str,
        identifier: Any,
        payload: Dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        encoded_id = _encode_identifier(identifier)
        response = self._request(
            "PATCH",
            f"/v1/{entity}/{encoded_id}",
            json_body=payload,
            idempotency_key=idempotency_key,
        )
        return _normalize_entity_response(entity, response)

    def delete(
        self,
        entity: str,
        identifier: Any,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        encoded_id = _encode_identifier(identifier)
        self._request(
            "DELETE",
            f"/v1/{entity}/{encoded_id}",
            idempotency_key=idempotency_key,
        )

    def transact(
        self,
        operations: Iterable[Dict[str, Any]],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        payload = {"ops": list(operations)}
        response = self._request(
            "POST",
            "/v1/_transact",
            json_body=payload,
            idempotency_key=idempotency_key,
        )
        if isinstance(response, dict) and "data" in response:
            normalized_items = []
            ops_list = payload["ops"]
            for idx, item in enumerate(response.get("data", [])):
                entity = ops_list[idx].get("entity", "") if idx < len(ops_list) else ""
                normalized_items.append(_normalize_entity_record(entity, item))
            return {**response, "data": normalized_items}
        return response

    def to_dict(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of the current settings (useful for debugging)."""

        return asdict(self._settings)
