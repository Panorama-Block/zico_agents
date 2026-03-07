import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import httpx  # noqa: F401
    import jwt  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(f"Missing runtime dependency: {exc}")

from src.integrations.panorama_gateway import PanoramaGatewayError, PanoramaGatewaySettings
from src.agents.lending.storage import LendingStateRepository
from src.agents.staking.storage import StakingStateRepository
from src.agents.strategy.storage import StrategyStateRepository


class _FakeGatewayClient:
    def __init__(self):
        self.calls = []
        self.raise_on_update = None
        self.raise_on_create = None
        self.raise_on_get = None
        self.raise_on_delete = None

    def get(self, entity, identifier):
        self.calls.append(("get", entity, identifier, None))
        if self.raise_on_get:
            raise self.raise_on_get
        return {"state": {"intent": {"action": "test"}, "status": "collecting"}}

    def update(self, entity, identifier, payload):
        self.calls.append(("update", entity, identifier, payload))
        if self.raise_on_update:
            raise self.raise_on_update
        return {"ok": True}

    def create(self, entity, payload):
        self.calls.append(("create", entity, None, payload))
        if self.raise_on_create:
            raise self.raise_on_create
        return {"ok": True}

    def delete(self, entity, identifier):
        self.calls.append(("delete", entity, identifier, None))
        if self.raise_on_delete:
            raise self.raise_on_delete
        return None

    def list(self, entity, query):
        self.calls.append(("list", entity, None, query))
        return {"data": []}


def _settings():
    return PanoramaGatewaySettings(
        base_url="http://gateway.local",
        jwt_secret="secret",
        tenant_id="tenant-agent",
        service_name="zico-agent",
        roles=["agent"],
    )


class SharedStateStorageTest(unittest.TestCase):
    def test_lending_upsert_uses_shared_state_entity(self):
        client = _FakeGatewayClient()
        client.raise_on_update = PanoramaGatewayError("not found", 404, {"error": "not_found"})
        repo = LendingStateRepository(client=client, settings=_settings())

        repo._upsert_session("u1", "c1", {"status": "collecting"})  # noqa: SLF001

        self.assertTrue(any(c[0] == "update" and c[1] == "agent-shared-states" for c in client.calls))
        create_calls = [c for c in client.calls if c[0] == "create" and c[1] == "agent-shared-states"]
        self.assertTrue(create_calls)
        payload = create_calls[0][3]
        self.assertEqual(payload["agentName"], "lending_agent")
        self.assertEqual(payload["userId"], "u1")
        self.assertEqual(payload["conversationId"], "c1")
        self.assertIn("state", payload)

    def test_staking_get_session_unwraps_state(self):
        client = _FakeGatewayClient()
        repo = StakingStateRepository(client=client, settings=_settings())

        session = repo._get_session("u2", "c2")  # noqa: SLF001
        self.assertIsInstance(session, dict)
        self.assertEqual(session.get("status"), "collecting")

        get_calls = [c for c in client.calls if c[0] == "get"]
        self.assertTrue(get_calls)
        self.assertEqual(get_calls[0][1], "agent-shared-states")
        self.assertEqual(get_calls[0][2], "staking_agent:u2:c2")

    def test_strategy_delete_uses_shared_state_identifier(self):
        client = _FakeGatewayClient()
        repo = StrategyStateRepository(client=client, settings=_settings())

        repo._delete_session("u3", "c3")  # noqa: SLF001
        delete_calls = [c for c in client.calls if c[0] == "delete"]
        self.assertTrue(delete_calls)
        self.assertEqual(delete_calls[0][1], "agent-shared-states")
        self.assertEqual(delete_calls[0][2], "strategy_agent:u3:c3")

    def test_lending_history_unknown_entity_falls_back_without_hard_fail(self):
        client = _FakeGatewayClient()
        client.raise_on_create = PanoramaGatewayError(
            "unknown entity",
            400,
            {"error": "validation_error", "message": "Unknown entity: lending-histories"},
        )
        repo = LendingStateRepository(client=client, settings=_settings())

        repo._create_history_entry("u4", "c4", {"status": "ok"})  # noqa: SLF001
        repo._create_history_entry("u4", "c4", {"status": "ok"})  # noqa: SLF001

        self.assertFalse(repo._remote_history_supported)  # noqa: SLF001
        create_calls = [c for c in client.calls if c[0] == "create" and c[1] == "lending-histories"]
        self.assertEqual(len(create_calls), 1)


if __name__ == "__main__":
    unittest.main()

