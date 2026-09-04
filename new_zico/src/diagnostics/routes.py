from __future__ import annotations

from fastapi import APIRouter

from src.diagnostics.runtime_evidence import build_runtime_evidence


router = APIRouter(tags=["diagnostics"])


@router.get("/__runtime_evidence", include_in_schema=False)
def runtime_evidence():
    """Temporary read-only architecture evidence endpoint.

    This route is intentionally source-controlled because the current
    Hugging Face deployment environment is not under PanoramaBlock control.
    It must be removed after the runtime evidence snapshot is collected.
    """
    return build_runtime_evidence()
