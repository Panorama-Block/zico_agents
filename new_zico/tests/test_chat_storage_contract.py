import os
import sys
import unittest
from datetime import datetime
from urllib.parse import quote

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import httpx
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(f"Missing runtime dependency: {exc}")

from src.integrations.panorama_gateway import PanoramaGatewayClient, PanoramaGatewayError, PanoramaGatewaySettings
from src.models.chatMessage import ChatMessage
from src.service.chat_manager import ChatManager, StoragePersistenceError
from src.service.panorama_store import PanoramaStore


def _settings() -> PanoramaGatewaySettings:
    return PanoramaGatewaySettings(
        base_url="http://gateway.local",
        jwt_secret="secret",
        tenant_id="tenant-agent",
        service_name="zico-agent",
        roles=["agent"],
    )


class _FakeStore:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.messages = []

    def ensure_user_and_conversation(self, user_id, conversation_id, **kwargs):
        if self.should_fail:
            raise RuntimeError("gateway down")
        return {}, {}

    def add_message(self, user_id, conversation_id, chat_message):
        if self.should_fail:
            raise RuntimeError("transact failed")
        payload = chat_message.dict()
        self.messages.append((user_id, conversation_id, payload))
        return payload


class _FakeGatewayClient:
    def __init__(self):
        self.calls = []

    def get(self, entity, identifier):
        self.calls.append(("get", entity, identifier, None))
        if entity == "conversations":
            return {
                "id": "legacy-row-id",
                "userId": "u1",
                "conversationId": "c1",
                "messageCount": 0,
                "tenantId": "tenant-agent",
            }
        raise AssertionError(f"Unexpected get for entity {entity}")

    def create(self, entity, payload):
        self.calls.append(("create", entity, None, payload))
        return payload

    def update(self, entity, identifier, payload):
        self.calls.append(("update", entity, identifier, payload))
        return {"ok": True}

    def transact(self, ops):
        self.calls.append(("transact", None, None, ops))
        return {"data": ops}

    def list(self, entity, query):
        self.calls.append(("list", entity, None, query))
        return {"data": []}


class ChatStorageContractTest(unittest.TestCase):
    def test_gateway_client_normalizes_conversation_ids(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path == "/v1/conversations/u1:c1":
                return httpx.Response(
                    200,
                    json={
                        "id": "legacy-row-id",
                        "userId": "u1",
                        "conversationId": "c1",
                        "messageCount": 3,
                    },
                )
            if request.method == "GET" and request.url.path == "/v1/conversations":
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": "legacy-row-id",
                                "userId": "u1",
                                "conversationId": "c1",
                                "messageCount": 3,
                            }
                        ]
                    },
                )
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")

        client = PanoramaGatewayClient(
            _settings(),
            client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://gateway.local"),
        )

        record = client.get("conversations", "u1:c1")
        self.assertEqual(record["id"], "u1:c1")
        self.assertEqual(record["messageCount"], 3)

        listed = client.list("conversations", {"where": {"userId": "u1"}})
        self.assertEqual(listed["data"][0]["id"], "u1:c1")

    def test_gateway_client_raises_on_malformed_conversation_payload(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "legacy-row-id", "messageCount": 1})

        client = PanoramaGatewayClient(
            _settings(),
            client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://gateway.local"),
        )

        with self.assertRaises(PanoramaGatewayError):
            client.get("conversations", "u1:c1")

    def test_gateway_client_encodes_colon_containing_composite_ids(self):
        encoded_id = f"{quote('0:abcd', safe='')}:{quote('c1', safe='')}"

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path == f"/v1/conversations/{encoded_id}":
                return httpx.Response(
                    200,
                    json={
                        "userId": "0:abcd",
                        "conversationId": "c1",
                        "messageCount": 1,
                    },
                )
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")

        client = PanoramaGatewayClient(
            _settings(),
            client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://gateway.local"),
        )

        record = client.get("conversations", {"userId": "0:abcd", "conversationId": "c1"})
        self.assertEqual(record["id"], encoded_id)
        self.assertEqual(record["userId"], "0:abcd")

    def test_panorama_store_updates_conversation_with_composite_key(self):
        gateway = _FakeGatewayClient()
        store = PanoramaStore(client=gateway, settings=_settings())

        message = ChatMessage(
            role="user",
            content="hello",
            timestamp=datetime.utcnow(),
        )
        store.add_message("u1", "c1", message)

        transact_calls = [call for call in gateway.calls if call[0] == "transact"]
        self.assertEqual(len(transact_calls), 1)
        ops = transact_calls[0][3]
        self.assertEqual(ops[1]["args"]["id"], {"userId": "u1", "conversationId": "c1"})

    def test_chat_manager_raises_on_persist_failure(self):
        manager = ChatManager(store=_FakeStore(should_fail=True))

        with self.assertRaises(StoragePersistenceError):
            manager.add_message(
                {"role": "user", "content": "hello"},
                conversation_id="c1",
                user_id="u1",
            )


if __name__ == "__main__":
    unittest.main()
