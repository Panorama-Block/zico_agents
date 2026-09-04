from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from src.diagnostics.routes import router


class StubResponse:
    def __init__(
        self,
        *,
        status_code: int,
        payload: Any = None,
        json_error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    return application


def request(
    app: FastAPI,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def _request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(
                "/__runtime_evidence",
                headers=headers,
            )

    return asyncio.run(_request())


def test_runtime_evidence_requires_authorization(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_URL",
        "https://api.panoramablock.com/database",
    )
    monkeypatch.delenv("AUTH_SERVICE_URL", raising=False)

    response = request(app)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    [
        "",
        "Basic abc",
        "Bearer",
        "Bearer ",
    ],
)
def test_runtime_evidence_rejects_malformed_authorization(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    authorization: str,
) -> None:
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_URL",
        "https://api.panoramablock.com/database",
    )
    monkeypatch.delenv("AUTH_SERVICE_URL", raising=False)

    response = request(
        app,
        headers={"Authorization": authorization},
    )

    assert response.status_code == 401


def test_runtime_evidence_derives_auth_origin_from_gateway_url(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_URL",
        "https://api.panoramablock.com/database",
    )
    monkeypatch.delenv("AUTH_SERVICE_URL", raising=False)

    observed: dict[str, Any] = {}

    def fake_post(url: str, *, json: dict[str, Any], timeout: float):
        observed["url"] = url
        observed["json"] = json
        observed["timeout"] = timeout
        return StubResponse(
            status_code=200,
            payload={
                "isValid": True,
                "payload": {"address": "0x1234"},
            },
        )

    import src.diagnostics.auth as diagnostic_auth

    monkeypatch.setattr(diagnostic_auth.httpx, "post", fake_post)

    response = request(
        app,
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert observed["url"] == "https://api.panoramablock.com/auth/validate"
    assert observed["json"] == {"token": "valid-token"}


def test_explicit_auth_service_url_takes_precedence(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AUTH_SERVICE_URL",
        "https://auth.example.test/",
    )
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_URL",
        "https://api.panoramablock.com/database",
    )

    observed: dict[str, Any] = {}

    def fake_post(url: str, *, json: dict[str, Any], timeout: float):
        observed["url"] = url
        return StubResponse(
            status_code=200,
            payload={
                "isValid": True,
                "payload": {"address": "0x1234"},
            },
        )

    import src.diagnostics.auth as diagnostic_auth

    monkeypatch.setattr(diagnostic_auth.httpx, "post", fake_post)

    response = request(
        app,
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert observed["url"] == "https://auth.example.test/auth/validate"


def test_invalid_panorama_token_returns_401(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_URL",
        "https://api.panoramablock.com/database",
    )
    monkeypatch.delenv("AUTH_SERVICE_URL", raising=False)

    def fake_post(url: str, *, json: dict[str, Any], timeout: float):
        return StubResponse(
            status_code=401,
            payload={"error": "Invalid authentication token"},
        )

    import src.diagnostics.auth as diagnostic_auth

    monkeypatch.setattr(diagnostic_auth.httpx, "post", fake_post)

    response = request(
        app,
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_auth_service_5xx_returns_503(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_URL",
        "https://api.panoramablock.com/database",
    )
    monkeypatch.delenv("AUTH_SERVICE_URL", raising=False)

    def fake_post(url: str, *, json: dict[str, Any], timeout: float):
        return StubResponse(
            status_code=500,
            payload={"error": "internal"},
        )

    import src.diagnostics.auth as diagnostic_auth

    monkeypatch.setattr(diagnostic_auth.httpx, "post", fake_post)

    response = request(
        app,
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 503


def test_invalid_auth_service_json_returns_503(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_URL",
        "https://api.panoramablock.com/database",
    )
    monkeypatch.delenv("AUTH_SERVICE_URL", raising=False)

    def fake_post(url: str, *, json: dict[str, Any], timeout: float):
        return StubResponse(
            status_code=200,
            json_error=ValueError("invalid json"),
        )

    import src.diagnostics.auth as diagnostic_auth

    monkeypatch.setattr(diagnostic_auth.httpx, "post", fake_post)

    response = request(
        app,
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 503


def test_missing_auth_configuration_fails_closed(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_SERVICE_URL", raising=False)
    monkeypatch.delenv("PANORAMA_GATEWAY_URL", raising=False)

    response = request(
        app,
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 503


def test_auth_service_isvalid_false_returns_401(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_URL",
        "https://api.panoramablock.com/database",
    )
    monkeypatch.delenv("AUTH_SERVICE_URL", raising=False)

    def fake_post(url: str, *, json: dict[str, Any], timeout: float):
        return StubResponse(
            status_code=200,
            payload={
                "isValid": False,
                "payload": {"address": "0x1234"},
            },
        )

    import src.diagnostics.auth as diagnostic_auth

    monkeypatch.setattr(diagnostic_auth.httpx, "post", fake_post)

    response = request(
        app,
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
