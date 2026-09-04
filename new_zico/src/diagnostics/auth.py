from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx
from fastapi import Header, HTTPException


@dataclass(frozen=True, slots=True)
class RuntimeEvidencePrincipal:
    """Authenticated Panorama principal allowed to inspect runtime evidence."""

    user_id: str


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _service_unavailable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=detail,
    )


def _resolve_auth_service_url() -> str:
    """Resolve Panorama auth without requiring HF environment changes.

    An explicitly configured AUTH_SERVICE_URL is authoritative.

    On legacy/uncontrolled deployments where it is absent, derive the
    Panorama public API origin from PANORAMA_GATEWAY_URL. For example:

        https://api.panoramablock.com/database
        -> https://api.panoramablock.com
    """

    explicit = (os.getenv("AUTH_SERVICE_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")

    gateway_url = (os.getenv("PANORAMA_GATEWAY_URL") or "").strip()
    if not gateway_url:
        raise _service_unavailable(
            "Authentication service is not configured."
        )

    parsed = urlsplit(gateway_url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _service_unavailable(
            "Authentication service is not configured."
        )

    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise _unauthorized()

    scheme, separator, token = authorization.partition(" ")

    if (
        not separator
        or scheme.lower() != "bearer"
        or not token.strip()
    ):
        raise _unauthorized()

    return token.strip()


def _extract_principal(payload: Mapping[str, Any]) -> RuntimeEvidencePrincipal:
    if payload.get("isValid") is not True:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_payload = payload.get("payload")
    if not isinstance(auth_payload, Mapping):
        raise _service_unavailable(
            "Authentication service returned an invalid response."
        )

    address = auth_payload.get("address")
    if not isinstance(address, str) or not address.strip():
        raise _service_unavailable(
            "Authentication service returned an invalid response."
        )

    return RuntimeEvidencePrincipal(
        user_id=address.strip().lower(),
    )


def require_runtime_evidence_principal(
    authorization: str | None = Header(default=None),
) -> RuntimeEvidencePrincipal:
    """Authenticate access to the runtime-evidence migration endpoint."""

    token = _parse_bearer_token(authorization)
    auth_service_url = _resolve_auth_service_url()

    try:
        response = httpx.post(
            f"{auth_service_url}/auth/validate",
            json={"token": token},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        raise _service_unavailable(
            "Authentication service is unavailable."
        ) from exc

    if response.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if response.status_code != 200:
        raise _service_unavailable(
            "Authentication service is unavailable."
        )

    try:
        payload = response.json()
    except Exception as exc:
        raise _service_unavailable(
            "Authentication service returned an invalid response."
        ) from exc

    if not isinstance(payload, Mapping):
        raise _service_unavailable(
            "Authentication service returned an invalid response."
        )

    return _extract_principal(payload)
