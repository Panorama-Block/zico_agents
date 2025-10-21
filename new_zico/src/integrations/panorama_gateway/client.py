from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from typing import Any, Dict, Iterable, Optional

import httpx
import jwt

from .config import PanoramaGatewaySettings, get_panorama_settings


class PanoramaGatewayError(RuntimeError):
    """Raised when the Panorama gateway returns an error response."""

    def __init__(self, message: str, status_code: int, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _encode_identifier(identifier: Any) -> str:
    """Coerce identifiers into the colon-delimited format expected by the gateway."""

    if isinstance(identifier, str):
        return identifier
    if isinstance(identifier, Iterable):
        parts: Iterable[str] = (str(part) for part in identifier)
        return ":".join(parts)
    if isinstance(identifier, dict):
        return ":".join(str(value) for value in identifier.values())
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

        response = self._client.request(
            method=method,
            url=path,
            headers=headers,
            params=params,
            json=json_body,
        )

        if response.status_code >= 400:
            message = f"Gateway request failed ({response.status_code})"
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            raise PanoramaGatewayError(message, response.status_code, payload)

        if response.status_code == 204:
            return None

        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.text

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
        return self._request("GET", f"/v1/{entity}", params=params)

    def get(self, entity: str, identifier: Any) -> Any:
        encoded_id = _encode_identifier(identifier)
        return self._request("GET", f"/v1/{entity}/{encoded_id}")

    def create(
        self,
        entity: str,
        payload: Dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        return self._request(
            "POST",
            f"/v1/{entity}",
            json_body=payload,
            idempotency_key=idempotency_key,
        )

    def update(
        self,
        entity: str,
        identifier: Any,
        payload: Dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        encoded_id = _encode_identifier(identifier)
        return self._request(
            "PATCH",
            f"/v1/{entity}/{encoded_id}",
            json_body=payload,
            idempotency_key=idempotency_key,
        )

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
        return self._request(
            "POST",
            "/v1/_transact",
            json_body=payload,
            idempotency_key=idempotency_key,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of the current settings (useful for debugging)."""

        return asdict(self._settings)
