import json

from src.diagnostics.routes import runtime_evidence


def test_runtime_evidence_endpoint_returns_evidence_without_runtime_flag(monkeypatch):
    monkeypatch.delenv("RUNTIME_EVIDENCE_ENABLED", raising=False)
    monkeypatch.setenv("PANORAMA_GATEWAY_URL", "https://gateway.example")
    monkeypatch.setenv(
        "PANORAMA_GATEWAY_JWT_SECRET",
        "dedicated-http-secret-material",
    )

    payload = runtime_evidence()

    assert payload["application"]["name"] == "Zico Agent API"
    assert payload["panorama_gateway"]["url"] == "https://gateway.example"
    assert (
        payload["panorama_gateway"]["effective_auth_mode"]
        == "dedicated-panorama-gateway-jwt"
    )


def test_serialized_http_payload_contains_no_secret_values(monkeypatch):
    secrets = {
        "PANORAMA_GATEWAY_JWT_SECRET": "dedicated-http-secret-material",
        "JWT_SECRET": "generic-http-secret-material",
        "OPENAI_API_KEY": "openai-http-secret-material",
        "ANTHROPIC_API_KEY": "anthropic-http-secret-material",
        "GEMINI_API_KEY": "gemini-http-secret-material",
        "TAVILY_API_KEY": "tavily-http-secret-material",
        "GLACIER_API_KEY": "glacier-http-secret-material",
        "REDIS_PASS": "redis-http-secret-material",
        "FUTURE_SIGNING_KEY": "future-http-secret-material",
        "UNKNOWN_RUNTIME_VALUE": "unknown-http-value-material",
    }

    for name, value in secrets.items():
        monkeypatch.setenv(name, value)

    payload = runtime_evidence()
    serialized = json.dumps(payload, sort_keys=True)

    for value in secrets.values():
        assert value not in serialized


def test_runtime_evidence_route_is_hidden_from_openapi():
    from src.diagnostics.routes import router

    route = next(
        route
        for route in router.routes
        if getattr(route, "path", None) == "/__runtime_evidence"
    )

    assert route.include_in_schema is False
