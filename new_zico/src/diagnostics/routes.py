from __future__ import annotations

from fastapi import APIRouter, Depends

from src.diagnostics.auth import (
    RuntimeEvidencePrincipal,
    require_runtime_evidence_principal,
)
from src.diagnostics.runtime_evidence import build_runtime_evidence


router = APIRouter(tags=["diagnostics"])


@router.get("/__runtime_evidence", include_in_schema=False)
def runtime_evidence(
    _principal: RuntimeEvidencePrincipal = Depends(
        require_runtime_evidence_principal
    ),
):
    """Authenticated, redacted runtime contract for migration verification.

    The endpoint is intentionally source-controlled so PanoramaBlock can
    inspect and compare runtime configuration even when the underlying
    hosting tenant is not under PanoramaBlock control.

    Authentication uses AUTH_SERVICE_URL when configured. On legacy
    deployments it derives the Panorama public API origin from the existing
    PANORAMA_GATEWAY_URL, avoiding a hosting-environment dependency.
    """

    return build_runtime_evidence()
