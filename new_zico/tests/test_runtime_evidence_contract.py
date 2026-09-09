import os

import pytest


SECRET_NAMES = {
    "JWT_SECRET",
    "PANORAMA_GATEWAY_JWT_SECRET",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "TAVILY_API_KEY",
    "GLACIER_API_KEY",
    "REDIS_PASS",
}


@pytest.fixture
def diagnostic_environment(monkeypatch):
    values = {
        "PANORAMA_GATEWAY_URL": "https://gateway.example",
        "PANORAMA_GATEWAY_TENANT": "tenant-agent",
        "PANORAMA_GATEWAY_SERVICE": "zico-agent",
        "PANORAMA_GATEWAY_ROLES": "agent,service",
        "PANORAMA_GATEWAY_TIMEOUT": "17",
        "PANORAMA_GATEWAY_JWT_AUDIENCE": "panorama-gateway",
        "PANORAMA_GATEWAY_JWT_ISSUER": "zico",
        "PANORAMA_GATEWAY_JWT_SECRET": "dedicated-secret-material",
        "JWT_SECRET": "generic-secret-material",
        "OPENAI_API_KEY": "openai-secret-material",
        "ANTHROPIC_API_KEY": "anthropic-secret-material",
        "GEMINI_API_KEY": "gemini-secret-material",
        "TAVILY_API_KEY": "tavily-secret-material",
        "GLACIER_API_KEY": "glacier-secret-material",
        "REDIS_PASS": "redis-secret-material",
        "REDIS_HOST": "redis.internal",
        "REDIS_PORT": "6379",
        "REDIS_TLS": "true",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "color",
        "DEFAULT_LLM_MODEL": "gemini-2.5-flash",
        "HF_SPACE_ID": "ColettoGS/zico-agent",
        "TEST_UNKNOWN_CONFIGURATION": "visible-non-secret-value",
    }

    for name, value in values.items():
        monkeypatch.setenv(name, value)

    return values


def test_runtime_evidence_never_exposes_secret_values(diagnostic_environment):
    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()
    serialized = repr(evidence)

    for name in SECRET_NAMES:
        secret_value = diagnostic_environment[name]
        assert secret_value not in serialized

        entry = evidence["environment"][name]
        assert entry["present"] is True
        assert entry["empty"] is False
        assert entry["length"] == len(secret_value)
        assert entry["redacted"] is True
        assert "value" not in entry


def test_runtime_evidence_reports_safe_configuration_values(diagnostic_environment):
    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()

    assert evidence["environment"]["PANORAMA_GATEWAY_URL"]["value"] == (
        "https://gateway.example"
    )
    assert evidence["environment"]["REDIS_HOST"]["value"] == "redis.internal"
    assert evidence["environment"]["LOG_LEVEL"]["value"] == "INFO"
    unknown = evidence["environment"]["TEST_UNKNOWN_CONFIGURATION"]
    assert unknown["present"] is True
    assert unknown["empty"] is False
    assert unknown["length"] == len("visible-non-secret-value")
    assert unknown["redacted"] is True
    assert "value" not in unknown


def test_runtime_evidence_reports_effective_gateway_contract(diagnostic_environment):
    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()
    gateway = evidence["panorama_gateway"]

    assert gateway["url"] == "https://gateway.example"
    assert gateway["tenant"] == "tenant-agent"
    assert gateway["service"] == "zico-agent"
    assert gateway["roles"] == ["agent", "service"]
    assert gateway["timeout"] == "17"
    assert gateway["jwt_audience"] == "panorama-gateway"
    assert gateway["jwt_issuer"] == "zico"

    assert gateway["dedicated_jwt_secret"]["present"] is True
    assert gateway["generic_jwt_secret"]["present"] is True
    assert gateway["effective_auth_mode"] == "dedicated-panorama-gateway-jwt"


def test_runtime_evidence_reports_legacy_runtime_without_loading_gateway(monkeypatch):
    monkeypatch.setenv("PANORAMA_GATEWAY_URL", "https://gateway.example")
    monkeypatch.delenv("PANORAMA_GATEWAY_JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "legacy-generic-secret")

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()
    gateway = evidence["panorama_gateway"]

    assert gateway["dedicated_jwt_secret"]["present"] is False
    assert gateway["generic_jwt_secret"]["present"] is True
    assert gateway["effective_auth_mode"] == "legacy-generic-jwt"


def test_runtime_evidence_reports_absent_gateway_auth(monkeypatch):
    monkeypatch.setenv("PANORAMA_GATEWAY_URL", "https://gateway.example")
    monkeypatch.delenv("PANORAMA_GATEWAY_JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()

    assert evidence["panorama_gateway"]["effective_auth_mode"] == "absent"


def test_secret_classifier_catches_unknown_credential_names(monkeypatch):
    monkeypatch.setenv("SOME_FUTURE_PRIVATE_KEY", "future-private-material")
    monkeypatch.setenv("ANOTHER_ACCESS_TOKEN", "future-token-material")
    monkeypatch.setenv("SERVICE_PASSWORD", "future-password-material")
    monkeypatch.setenv("DATABASE_CONNECTION_STRING", "future-connection-material")
    monkeypatch.setenv("AUTHORIZATION_HEADER", "future-auth-material")

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()
    serialized = repr(evidence)

    for value in (
        "future-private-material",
        "future-token-material",
        "future-password-material",
        "future-connection-material",
        "future-auth-material",
    ):
        assert value not in serialized


def test_runtime_evidence_contains_runtime_identity(diagnostic_environment):
    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()

    runtime = evidence["runtime"]

    assert runtime["python_version"]
    assert runtime["platform"]
    assert runtime["machine"] is not None
    assert runtime["hostname"]
    assert runtime["working_directory"]
    assert isinstance(runtime["argv"], dict)
    assert runtime["argv"]["count"] >= 1
    assert "command" in runtime["argv"]
    assert runtime["argv"]["arguments_redacted"] >= 0

    assert evidence["application"]["name"] == "Zico Agent API"
    assert evidence["application"]["version"] == "3.0"


def test_runtime_evidence_is_read_only(monkeypatch):
    monkeypatch.setenv("PANORAMA_GATEWAY_URL", "https://gateway.example")
    monkeypatch.setenv("PANORAMA_GATEWAY_JWT_SECRET", "secret-material")

    before = dict(os.environ)

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    build_runtime_evidence()

    after = dict(os.environ)

    assert after == before


def test_runtime_evidence_does_not_expose_command_line_arguments(monkeypatch):
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uvicorn",
            "src.app:app",
            "--token",
            "command-line-secret-material",
        ],
    )

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()
    serialized = repr(evidence)

    assert "command-line-secret-material" not in serialized
    assert evidence["runtime"]["argv"]["count"] == 4
    assert evidence["runtime"]["argv"]["command"] == "uvicorn"
    assert evidence["runtime"]["argv"]["arguments_redacted"] == 3



def test_hf_platform_identity_is_control_plane_metadata(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "ColettoGS/zico-agent")
    monkeypatch.setenv("SPACE_AUTHOR_NAME", "ColettoGS")
    monkeypatch.setenv("SPACE_REPO_NAME", "zico-agent")

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()

    for name in ("SPACE_ID", "SPACE_AUTHOR_NAME", "SPACE_REPO_NAME"):
        entry = evidence["environment"][name]
        assert entry["classification"] == "huggingface-system"
        assert entry["migration"] == "REQUIRES_PLATFORM_CONTROL_PLANE"
        assert entry["redacted"] is False


def test_application_configuration_is_replicable_from_export(monkeypatch):
    monkeypatch.setenv("PANORAMA_GATEWAY_URL", "https://gateway.example")

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()
    entry = evidence["environment"]["PANORAMA_GATEWAY_URL"]

    assert entry["classification"] == "configuration"
    assert entry["migration"] == "REPLICABLE_FROM_EXPORT"
    assert entry["redacted"] is False
    assert entry["value"] == "https://gateway.example"


def test_application_secret_has_stable_huggingface_migration_reference(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "ColettoGS/zico-agent")
    monkeypatch.setenv("GEMINI_API_KEY", "migration-secret-material")

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()
    entry = evidence["environment"]["GEMINI_API_KEY"]

    assert entry["classification"] == "secret"
    assert entry["migration"] == "REQUIRES_SECRET_RECOVERY"
    assert entry["redacted"] is True
    assert "value" not in entry
    assert entry["secretMigration"] == {
        "secretRef": "huggingface:ColettoGS/zico-agent:GEMINI_API_KEY",
        "valueSource": "huggingface-space-secret",
        "recoveryAction": "RECOVER_OR_ROTATE_SECRET",
    }

    assert "migration-secret-material" not in repr(evidence)


def test_redis_url_is_treated_as_credential_bearing(monkeypatch):
    redis_url = "redis://runtime-user:runtime-password@redis.internal:6379/0"
    monkeypatch.setenv("REDIS_URL", redis_url)

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()
    entry = evidence["environment"]["REDIS_URL"]

    assert entry["classification"] == "secret"
    assert entry["migration"] == "REQUIRES_SECRET_RECOVERY"
    assert entry["redacted"] is True
    assert "value" not in entry
    assert entry["secretMigration"]["secretRef"].endswith(":REDIS_URL")
    assert entry["secretMigration"]["recoveryAction"] == "RECOVER_OR_ROTATE_SECRET"
    assert redis_url not in repr(evidence)



def test_production_huggingface_metadata_is_control_plane_state(monkeypatch):
    platform_values = {
        "ACCELERATOR": "cpu",
        "COMMIT_SHA": "a" * 40,
        "CPU_CORES": "2",
        "IMAGE_SHA": "b" * 40,
        "MEMORY": "16GiB",
        "SPACE_AUTHOR_NAME": "ColettoGS",
        "SPACE_CREATOR_USER_ID": "production-user-id",
        "SPACE_HOST": "colettogs-zico-agent.hf.space",
        "SPACE_ID": "ColettoGS/zico-agent",
        "SPACE_REPO_NAME": "zico-agent",
        "SPACE_SUBDOMAIN": "colettogs-zico-agent",
        "SPACE_TITLE": "zico-agent",
    }

    for name, value in platform_values.items():
        monkeypatch.setenv(name, value)

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()

    for name, value in platform_values.items():
        entry = evidence["environment"][name]
        assert entry["classification"] == "huggingface-system"
        assert entry["migration"] == "REQUIRES_PLATFORM_CONTROL_PLANE"
        assert entry["redacted"] is False
        assert entry["value"] == value


def test_platform_classification_does_not_expose_runtime_internals(monkeypatch):
    runtime_values = {
        "HOME": "/home/user",
        "HOSTNAME": "runtime-host",
        "KUBERNETES_SERVICE_HOST": "10.0.0.1",
        "PATH": "/usr/local/bin",
        "PWD": "/app",
        "PYTHONPATH": "/app",
    }

    for name, value in runtime_values.items():
        monkeypatch.setenv(name, value)

    from src.diagnostics.runtime_evidence import build_runtime_evidence

    evidence = build_runtime_evidence()
    serialized = repr(evidence)

    for name, value in runtime_values.items():
        entry = evidence["environment"][name]
        assert entry["classification"] == "runtime"
        assert entry["migration"] == "OBSERVATIONAL_ONLY"
        assert entry["redacted"] is True
        assert "value" not in entry
        assert value not in serialized
