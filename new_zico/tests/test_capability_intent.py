"""Tests for src/models/capability_intent.py (card #70).

Covers the 5 capabilities the card called out (swap, liquidity, lending,
staking, automation [aka 'dca' in older zico vocabulary]) plus the validators
and the camelCase wire renderer.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.models.capability_intent import CapabilityIntent


TRACE = UUID("11111111-1111-4111-8111-111111111111")
IDEMP = UUID("22222222-2222-4222-8222-222222222222")
USER = "0x" + "ab" * 20
TENANT = "tenant-agent"


def _base(**overrides):
    return {
        "capability": "swap",
        "action": "prepare-swap",
        "chain_id": 8453,
        "user_address": USER,
        "payload": {"tokenIn": "0xeeee", "amountIn": "1000000000000000000"},
        "tenant_id": TENANT,
        "trace_id": TRACE,
        **overrides,
    }


# ---------------------------------------------------------------------------
# Happy path — every capability the card called out
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "capability,action,payload",
    [
        ("swap", "prepare-swap", {"tokenIn": "0xeeee", "amountIn": "1"}),
        ("liquidity", "prepare-add", {"poolId": "0xpool", "amountA": "1"}),
        ("lending", "prepare-borrow", {"asset": "USDC", "amount": "100"}),
        ("staking", "prepare-stake", {"amount": "1000000000000000000"}),
        # 'dca' from older zico vocabulary maps to the 'automation' slug
        # in shared/capability/provider.types.ts (CAPABILITY_SLUGS).
        ("automation", "schedule-dca", {"frequency": "weekly", "amount": "100"}),
    ],
)
def test_intent_round_trip_per_capability(capability, action, payload):
    intent = CapabilityIntent(**_base(capability=capability, action=action, payload=payload))
    assert intent.capability == capability
    assert intent.action == action

    wire = intent.to_capability_request()
    assert wire == {
        "tenantId": TENANT,
        "traceId": str(TRACE),
        "chainId": 8453,
        "userAddress": USER,
        "payload": payload,
    }
    assert intent.endpoint_path() == f"/v1/capability/{capability}/{action}"


def test_idempotency_key_passes_through_when_set():
    intent = CapabilityIntent(**_base(idempotency_key=IDEMP))
    wire = intent.to_capability_request()
    assert wire["idempotencyKey"] == str(IDEMP)


def test_idempotency_key_omitted_when_unset():
    intent = CapabilityIntent(**_base())
    assert "idempotencyKey" not in intent.to_capability_request()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rejects_unknown_capability_slug():
    with pytest.raises(ValidationError):
        CapabilityIntent(**_base(capability="degen"))


def test_rejects_non_evm_address():
    with pytest.raises(ValidationError) as exc:
        CapabilityIntent(**_base(user_address="not-an-address"))
    assert "user_address" in str(exc.value)


def test_rejects_address_wrong_length():
    with pytest.raises(ValidationError):
        CapabilityIntent(**_base(user_address="0xabc"))


def test_rejects_non_hex_address():
    with pytest.raises(ValidationError):
        CapabilityIntent(**_base(user_address="0x" + "zz" * 20))


def test_rejects_non_positive_chain_id():
    with pytest.raises(ValidationError):
        CapabilityIntent(**_base(chain_id=0))


def test_rejects_action_with_invalid_chars():
    with pytest.raises(ValidationError):
        CapabilityIntent(**_base(action="prepare swap"))


def test_rejects_empty_tenant_id():
    with pytest.raises(ValidationError):
        CapabilityIntent(**_base(tenant_id=""))


def test_rejects_extra_unknown_field():
    # model_config extra='forbid' — agents must not smuggle protocol names through.
    with pytest.raises(ValidationError):
        CapabilityIntent(**_base(provider="aerodrome"))


def test_intent_is_immutable():
    intent = CapabilityIntent(**_base())
    with pytest.raises(ValidationError):
        intent.capability = "lending"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Trace id flexibility
# ---------------------------------------------------------------------------


def test_accepts_uuid_as_string():
    intent = CapabilityIntent(**_base(trace_id=str(uuid4())))
    assert isinstance(intent.trace_id, UUID)
