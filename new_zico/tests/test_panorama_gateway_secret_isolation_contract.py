import pytest

from src.integrations.panorama_gateway.config import PanoramaGatewaySettings


def test_gateway_requires_dedicated_panorama_gateway_secret(monkeypatch):
    monkeypatch.setenv("PANORAMA_GATEWAY_URL", "https://gateway.example")
    monkeypatch.delenv("PANORAMA_GATEWAY_JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "generic-application-jwt-secret")

    with pytest.raises(
        ValueError,
        match="PANORAMA_GATEWAY_JWT_SECRET environment variable is required",
    ):
        PanoramaGatewaySettings.load()


def test_gateway_accepts_dedicated_panorama_gateway_secret(monkeypatch):
    monkeypatch.setenv("PANORAMA_GATEWAY_URL", "https://gateway.example")
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_JWT_SECRET",
        "dedicated-gateway-signing-secret",
    )
    monkeypatch.setenv("JWT_SECRET", "generic-application-jwt-secret")

    settings = PanoramaGatewaySettings.load()

    assert settings.jwt_secret == "dedicated-gateway-signing-secret"
