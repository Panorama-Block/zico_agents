from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional


def _split_roles(raw: str | None) -> List[str]:
    if not raw:
        return ["agent"]
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(slots=True)
class PanoramaGatewaySettings:
    """Runtime configuration for the Panorama data gateway client."""

    base_url: str
    jwt_secret: str
    tenant_id: str = "tenant-agent"
    service_name: str = "zico-agent"
    roles: List[str] = field(default_factory=lambda: ["agent"])
    jwt_audience: Optional[str] = None
    jwt_issuer: Optional[str] = None
    request_timeout: float = 10.0

    @classmethod
    def load(cls) -> "PanoramaGatewaySettings":
        base_url = os.getenv("PANORAMA_GATEWAY_URL")
        if not base_url:
            raise ValueError("PANORAMA_GATEWAY_URL environment variable is required.")

        secret = os.getenv("PANORAMA_GATEWAY_JWT_SECRET") or os.getenv("JWT_SECRET")
        if not secret:
            raise ValueError(
                "Set PANORAMA_GATEWAY_JWT_SECRET or reuse JWT_SECRET for Panorama gateway auth."
            )

        return cls(
            base_url=base_url.rstrip("/"),
            jwt_secret=secret,
            tenant_id=os.getenv("PANORAMA_GATEWAY_TENANT", "tenant-agent"),
            service_name=os.getenv("PANORAMA_GATEWAY_SERVICE", "zico-agent"),
            roles=_split_roles(os.getenv("PANORAMA_GATEWAY_ROLES", "agent")),
            jwt_audience=os.getenv("PANORAMA_GATEWAY_JWT_AUDIENCE"),
            jwt_issuer=os.getenv("PANORAMA_GATEWAY_JWT_ISSUER"),
            request_timeout=float(os.getenv("PANORAMA_GATEWAY_TIMEOUT", "10")),
        )


@lru_cache(maxsize=1)
def get_panorama_settings() -> PanoramaGatewaySettings:
    """Memoized accessor so callers share a single settings instance."""

    return PanoramaGatewaySettings.load()
