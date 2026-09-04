from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import httpx
from fastapi import Header, HTTPException


class ChatAuthError(RuntimeError):
    """Raised when the supplied end-user authentication is invalid."""


class ChatAuthUnavailableError(RuntimeError):
    """Raised when the Panorama auth service cannot validate a token."""


@dataclass(frozen=True, slots=True)
class PanoramaPrincipal:
    """Authenticated Panorama end-user principal."""

    user_id: str


def _normalise_address(value: Any) -> str:
    if not isinstance(value, str):
        raise ChatAuthError("Authenticated principal address is missing.")

    address = value.strip()
    if not address:
        raise ChatAuthError("Authenticated principal address is missing.")

    return address.lower()


def validate_bearer_token(
    token: str,
    *,
    auth_service_url: str,
    client: httpx.Client | Any | None = None,
) -> PanoramaPrincipal:
    """Validate an end-user bearer token with Panorama auth-service."""

    cleaned_token = token.strip()
    if not cleaned_token:
        raise ChatAuthError("Bearer token is missing.")

    base_url = auth_service_url.rstrip("/")
    if not base_url:
        raise ChatAuthUnavailableError("Panorama auth service URL is not configured.")

    owns_client = client is None
    http_client = client or httpx.Client(timeout=10.0)

    try:
        try:
            response = http_client.post(
                f"{base_url}/auth/validate",
                json={"token": cleaned_token},
            )
        except Exception as exc:
            raise ChatAuthUnavailableError(
                "Panorama auth service is unavailable."
            ) from exc

        if response.status_code != 200:
            raise ChatAuthError("Bearer token is invalid.")

        try:
            payload: Mapping[str, Any] = response.json()
        except Exception as exc:
            raise ChatAuthUnavailableError(
                "Panorama auth service returned an invalid response."
            ) from exc

        if payload.get("isValid") is not True:
            raise ChatAuthError("Bearer token is invalid.")

        auth_payload = payload.get("payload")
        if not isinstance(auth_payload, Mapping):
            raise ChatAuthError("Authenticated principal is missing.")

        address = _normalise_address(auth_payload.get("address"))
        return PanoramaPrincipal(user_id=address)
    finally:
        if owns_client:
            http_client.close()


def require_chat_principal(
    authorization: str | None = Header(default=None),
) -> PanoramaPrincipal:
    """FastAPI dependency resolving the authenticated chat principal."""

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, separator, token = authorization.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not token.strip()
    ):
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service_url = (os.getenv("AUTH_SERVICE_URL") or "").strip()
    if not auth_service_url:
        raise HTTPException(
            status_code=503,
            detail="Authentication service is not configured.",
        )

    try:
        return validate_bearer_token(
            token,
            auth_service_url=auth_service_url,
        )
    except ChatAuthError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except ChatAuthUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication service is unavailable.",
        ) from exc
