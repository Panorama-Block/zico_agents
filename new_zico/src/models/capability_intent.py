"""CapabilityIntent — agent → backend capability call schema.

Every Zico agent that proposes a state-mutating action emits a `CapabilityIntent`.
The intent maps 1:1 to the backend `CapabilityRequest<T>` envelope owned by the
`@panorama/capability` shared package (cards #199-#203). Extra fields `capability`
and `action` identify the target endpoint `/v1/capability/<capability>/<action>`;
they live in the URL on the wire and are stripped by `to_capability_request()`.

See `docs/agent-capability-contract.md` for the surrounding contract.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Closed set mirroring shared/capability/provider.types.ts CAPABILITY_SLUGS.
# Update both sides together when adding a new capability.
CapabilitySlug = Literal[
    "swap",
    "lending",
    "staking",
    "liquidity",
    "bridge",
    "automation",
    "auth",
]


class CapabilityIntent(BaseModel):
    """Agent-emitted intent ready to be dispatched to a capability endpoint.

    Fields use snake_case (Python convention); `to_capability_request()` rewrites
    them to camelCase to match the backend envelope.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: CapabilitySlug = Field(
        ..., description="Target capability slug; controls the URL path."
    )
    action: str = Field(
        ...,
        min_length=1,
        description="Action name inside the capability (e.g. 'prepare-swap').",
    )
    chain_id: int = Field(..., gt=0, description="EIP-155 chain id.")
    user_address: str = Field(
        ..., description="EVM address of the user, 0x-prefixed hex string."
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific payload (typed by the consumer).",
    )
    tenant_id: str = Field(..., min_length=1)
    trace_id: UUID = Field(..., description="RFC 4122 UUID for distributed tracing.")
    idempotency_key: Optional[UUID] = Field(
        default=None,
        description="Required by state-mutating actions; hash(key+body) caches the response.",
    )

    @field_validator("user_address")
    @classmethod
    def _validate_user_address(cls, value: str) -> str:
        if not value.startswith("0x") or len(value) != 42:
            raise ValueError(
                "user_address must be a 0x-prefixed 42-char EVM address"
            )
        try:
            int(value, 16)
        except ValueError as err:
            raise ValueError("user_address must be hex-decodable") from err
        return value

    @field_validator("action")
    @classmethod
    def _validate_action(cls, value: str) -> str:
        # Lowercase kebab/letters/digits — matches CONVENTIONS.md §6 for action names.
        if not all(ch.isalnum() or ch in "-_" for ch in value):
            raise ValueError(
                "action must contain only alphanumerics, '-' or '_'"
            )
        return value

    def to_capability_request(self) -> Dict[str, Any]:
        """Render the camelCase wire payload for POST /v1/capability/<cap>/<action>.

        The router strips `capability` and `action` — they're already in the URL.
        """
        wire: Dict[str, Any] = {
            "tenantId": self.tenant_id,
            "traceId": str(self.trace_id),
            "chainId": self.chain_id,
            "userAddress": self.user_address,
            "payload": self.payload,
        }
        if self.idempotency_key is not None:
            wire["idempotencyKey"] = str(self.idempotency_key)
        return wire

    def endpoint_path(self) -> str:
        """Return the URL path the dispatcher should POST to."""
        return f"/v1/capability/{self.capability}/{self.action}"


__all__ = ["CapabilityIntent", "CapabilitySlug"]
