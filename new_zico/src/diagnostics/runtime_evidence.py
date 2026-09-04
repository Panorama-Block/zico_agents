from __future__ import annotations

import os
import platform
import socket
import sys
from importlib import metadata
from pathlib import Path
from typing import Any


APPLICATION_NAME = "Zico Agent API"
APPLICATION_VERSION = "3.0"


# Values for these variables are useful for architecture discovery and are
# considered configuration rather than credentials. Everything else is
# redacted by default.
SAFE_VALUE_NAMES = {
    "AUTH_SERVICE_URL",
    "DEFAULT_LLM_MODEL",
    "DEFAULT_LLM_TEMPERATURE",
    "EMBEDDING_MODEL",
    "HF_SPACE_ID",
    "HF_SPACE_AUTHOR_NAME",
    "HF_SPACE_REPO_NAME",
    "HF_SPACE_HOST",
    "LOG_FORMAT",
    "LOG_LEVEL",
    "PANORAMA_GATEWAY_JWT_AUDIENCE",
    "PANORAMA_GATEWAY_JWT_ISSUER",
    "PANORAMA_GATEWAY_ROLES",
    "PANORAMA_GATEWAY_SERVICE",
    "PANORAMA_GATEWAY_TENANT",
    "PANORAMA_GATEWAY_TIMEOUT",
    "PANORAMA_GATEWAY_URL",
    "RATE_LIMIT_CHAT",
    "RATE_LIMIT_DEFAULT",
    "RATE_LIMIT_HEALTH",
    "RATE_LIMIT_STREAM",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_TLS",
    "SPACE_AUTHOR_NAME",
    "SPACE_ID",
    "SPACE_REPO_NAME",
    "STRATEGY_AGENT_ENABLED",
    "STRATEGY_DEFAULT_NETWORK",
    "STRATEGY_LIVE_DATA_ERROR_TTL_SEC",
    "STRATEGY_LIVE_DATA_STALE_TTL_SEC",
    "STRATEGY_LIVE_DATA_TTL_SEC",
    "YIELD_EXECUTION_API_BASE",
    "YIELD_EXECUTION_API_BASES",
}


# Any match here is always treated as secret material even if somebody later
# accidentally adds the variable to SAFE_VALUE_NAMES.
SECRET_NAME_MARKERS = (
    "API_KEY",
    "APIKEY",
    "AUTHORIZATION",
    "BEARER",
    "CERT",
    "CONNECTION_STRING",
    "COOKIE",
    "CREDENTIAL",
    "ENCRYPTION",
    "JWT",
    "KEY",
    "MNEMONIC",
    "PASS",
    "PASSWORD",
    "PRIVATE",
    "SECRET",
    "SIGNATURE",
    "TOKEN",
)


PACKAGE_NAMES = (
    "fastapi",
    "uvicorn",
    "pydantic",
    "httpx",
)


def _is_secret_name(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in SECRET_NAME_MARKERS)


def _presence(name: str) -> dict[str, Any]:
    value = os.environ.get(name)
    present = name in os.environ

    return {
        "present": present,
        "empty": present and value == "",
        "length": len(value) if value is not None else 0,
        "redacted": True,
    }


def _environment_entry(name: str, value: str) -> dict[str, Any]:
    base = {
        "present": True,
        "empty": value == "",
        "length": len(value),
    }

    if _is_secret_name(name):
        return {
            **base,
            "redacted": True,
        }

    if name in SAFE_VALUE_NAMES:
        return {
            **base,
            "redacted": False,
            "value": value,
        }

    # Unknown variables are deliberately metadata-only. This is safer than
    # attempting to infer whether an unfamiliar variable contains a secret.
    return {
        **base,
        "redacted": True,
    }


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}

    for package_name in PACKAGE_NAMES:
        try:
            versions[package_name] = metadata.version(package_name)
        except metadata.PackageNotFoundError:
            versions[package_name] = None

    return versions


def _split_roles(raw: str | None) -> list[str]:
    if not raw:
        return ["agent"]
    return [part.strip() for part in raw.split(",") if part.strip()]


def _effective_gateway_auth_mode() -> str:
    if os.environ.get("PANORAMA_GATEWAY_JWT_SECRET"):
        return "dedicated-panorama-gateway-jwt"

    if os.environ.get("JWT_SECRET"):
        return "legacy-generic-jwt"

    return "absent"


def build_runtime_evidence() -> dict[str, Any]:
    """Build a read-only, secret-redacted snapshot of the current runtime."""

    environment = {
        name: _environment_entry(name, value)
        for name, value in sorted(os.environ.items())
    }

    panorama_gateway = {
        "url": os.environ.get("PANORAMA_GATEWAY_URL"),
        "tenant": os.environ.get("PANORAMA_GATEWAY_TENANT", "tenant-agent"),
        "service": os.environ.get("PANORAMA_GATEWAY_SERVICE", "zico-agent"),
        "roles": _split_roles(os.environ.get("PANORAMA_GATEWAY_ROLES", "agent")),
        "timeout": os.environ.get("PANORAMA_GATEWAY_TIMEOUT", "10"),
        "jwt_audience": os.environ.get("PANORAMA_GATEWAY_JWT_AUDIENCE"),
        "jwt_issuer": os.environ.get("PANORAMA_GATEWAY_JWT_ISSUER"),
        "dedicated_jwt_secret": _presence("PANORAMA_GATEWAY_JWT_SECRET"),
        "generic_jwt_secret": _presence("JWT_SECRET"),
        "effective_auth_mode": _effective_gateway_auth_mode(),
    }

    return {
        "application": {
            "name": APPLICATION_NAME,
            "version": APPLICATION_VERSION,
        },
        "runtime": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "hostname": socket.gethostname(),
            "working_directory": str(Path.cwd()),
            "executable": sys.executable,
            "argv": {
                "count": len(sys.argv),
                "command": Path(sys.argv[0]).name if sys.argv else None,
                "arguments_redacted": max(len(sys.argv) - 1, 0),
            },
            "packages": _package_versions(),
        },
        "environment": environment,
        "panorama_gateway": panorama_gateway,
    }
