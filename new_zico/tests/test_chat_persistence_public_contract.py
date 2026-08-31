import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.service.chat_manager import ChatManager, ConversationNotFoundError
from src.service.chat_persistence_store import ChatPersistenceStore


class FakeGateway:
    def __init__(self):
        self.calls = []
        self.deleted = False

    def list(self, entity, query):
        self.calls.append(("list", entity, query))
        where = query.get("where", {})
        if entity == "conversations":
            return {
                "data": [
                    {
                        "id": "u1:conversation-123",
                        "userId": "u1",
                        "conversationId": "conversation-123",
                        "title": "Swap AVAX to USDC",
                        "messageCount": 2,
                        "updatedAt": "2026-08-31T12:00:00.000Z",
                    }
                ]
            }
        if entity == "messages":
            return {
                "data": [
                    {
                        "messageId": "m1",
                        "userId": "u1",
                        "conversationId": "conversation-123",
                        "role": "user",
                        "content": "hello",
                    }
                ]
            }
        if entity == "message-tool-calls" and where.get("messageId") == "m1":
            return {"data": [{"toolCallId": "tc1", "messageId": "m1"}]}
        if entity == "conversation-memories":
            return {"data": [{"memoryId": "mem1"}]}
        if entity == "agent-shared-states":
            return {"data": [{"agentName": "swap_agent"}]}
        if entity == "swap-sessions":
            return {"data": [{"userId": "u1", "conversationId": "conversation-123"}]}
        if entity == "dca-sessions":
            return {"data": []}
        return {"data": []}

    def get(self, entity, identifier):
        self.calls.append(("get", entity, identifier))
        if self.deleted:
            from src.integrations.panorama_gateway import PanoramaGatewayError
            raise PanoramaGatewayError("not found", 404)
        return {
            "userId": "u1",
            "conversationId": "conversation-123",
            "messageCount": 1,
        }

    def transact(self, operations):
        self.calls.append(("transact", operations))
        return {"data": operations}

    def delete(self, entity, identifier):
        self.calls.append(("delete", entity, identifier))
        self.deleted = True

    def update(self, entity, identifier, payload):
        self.calls.append(("update", entity, identifier, payload))
        return payload


class ReadOnlyStore:
    def __init__(self):
        self.list_calls = []
        self.ensure_calls = 0

    def list_messages(self, user_id, conversation_id):
        self.list_calls.append((user_id, conversation_id))
        return [{"role": "user", "content": "persisted"}]

    def ensure_conversation(self, *args, **kwargs):
        self.ensure_calls += 1
        raise AssertionError("GET history must not create or ensure a conversation")


class DeleteMissingStore:
    def delete_conversation(self, user_id, conversation_id):
        return False


class ChatPersistencePublicContractTest(unittest.TestCase):
    def test_list_exposes_domain_conversation_id_not_gateway_composite_id(self):
        gateway = FakeGateway()
        store = ChatPersistenceStore(client=gateway)

        conversations = store.list_conversations("u1")

        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0]["id"], "conversation-123")
        self.assertEqual(conversations[0]["conversation_id"], "conversation-123")
        self.assertNotEqual(conversations[0]["id"], "u1:conversation-123")

    def test_history_read_is_non_mutating(self):
        store = ReadOnlyStore()
        manager = ChatManager(store=store)

        history = manager.get_messages("conversation-123", "u1")

        self.assertEqual(history[0]["content"], "persisted")
        self.assertEqual(store.ensure_calls, 0)
        self.assertEqual(store.list_calls, [("u1", "conversation-123")])

    def test_delete_removes_fk_dependents_before_messages_and_conversation(self):
        gateway = FakeGateway()
        store = ChatPersistenceStore(client=gateway)

        deleted = store.delete_conversation("u1", "conversation-123")

        self.assertTrue(deleted)
        transact = next(call for call in gateway.calls if call[0] == "transact")
        operations = transact[1]
        tool_call_index = next(
            index for index, op in enumerate(operations)
            if op["entity"] == "message-tool-calls"
        )
        message_index = next(
            index for index, op in enumerate(operations)
            if op["entity"] == "messages"
        )
        self.assertLess(tool_call_index, message_index)
        self.assertTrue(any(op["entity"] == "conversation-memories" for op in operations))
        self.assertTrue(any(op["entity"] == "agent-shared-states" for op in operations))
        self.assertTrue(any(op["entity"] == "swap-sessions" for op in operations))
        self.assertEqual(gateway.calls[-1][0], "delete")
        self.assertEqual(gateway.calls[-1][1], "conversations")

    def test_delete_missing_conversation_is_not_reported_as_success(self):
        manager = ChatManager(store=DeleteMissingStore())

        with self.assertRaises(ConversationNotFoundError):
            manager.delete_conversation("missing", "u1")


if __name__ == "__main__":
    unittest.main()
