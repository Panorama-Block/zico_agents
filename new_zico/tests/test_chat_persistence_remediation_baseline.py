import os
import sys
import unittest
from unittest.mock import MagicMock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.integrations.panorama_gateway import PanoramaGatewaySettings
from src.service.chat_manager import ChatManager
from src.service.panorama_store import PanoramaStore


def _settings() -> PanoramaGatewaySettings:
    return PanoramaGatewaySettings(
        base_url="http://gateway.local",
        jwt_secret="test-secret",
        tenant_id="tenant-agent",
        service_name="zico-agent",
        roles=["agent"],
    )


class _ListGateway:
    """
    Simulates what PanoramaGatewayClient currently returns after
    normalising a conversation resource.

    Logical conversation ID:
        conversation-abc

    Gateway resource ID:
        user-123:conversation-abc
    """

    def list(self, entity, query):
        if entity != "conversations":
            raise AssertionError(f"Unexpected entity: {entity}")

        return {
            "data": [
                {
                    "id": "user-123:conversation-abc",
                    "userId": "user-123",
                    "conversationId": "conversation-abc",
                    "title": "My persisted conversation",
                    "messageCount": 4,
                    "updatedAt": "2026-09-03T10:00:00.000Z",
                }
            ]
        }


class ChatPersistenceRemediationBaselineTest(unittest.TestCase):
    def test_list_conversations_exposes_logical_conversation_id(self):
        store = PanoramaStore(
            client=_ListGateway(),
            settings=_settings(),
        )

        conversations = store.list_conversations("user-123")

        self.assertEqual(len(conversations), 1)

        conversation = conversations[0]

        # Application-facing conversation identity must be the logical
        # conversationId. The gateway resource ID is an internal detail.
        self.assertEqual(
            conversation["id"],
            "conversation-abc",
        )
        self.assertNotEqual(
            conversation["id"],
            "user-123:conversation-abc",
        )

    def test_get_messages_is_read_only(self):
        store = MagicMock()

        store.list_messages.return_value = [
            {
                "role": "user",
                "content": "hello",
            }
        ]

        manager = ChatManager(store=store)

        result = manager.get_messages(
            conversation_id="conversation-abc",
            user_id="user-123",
        )

        self.assertEqual(len(result), 1)

        # History retrieval must not create or ensure persistent state.
        store.ensure_conversation.assert_not_called()

        store.list_messages.assert_called_once_with(
            "user-123",
            "conversation-abc",
        )

    def test_delete_failure_is_not_reported_as_success(self):
        store = MagicMock()

        store.delete_conversation.side_effect = RuntimeError(
            "database delete failed"
        )

        manager = ChatManager(store=store)

        # Durable deletion failure must propagate so that the HTTP route
        # cannot report success and the client cannot remove local state.
        with self.assertRaisesRegex(
            RuntimeError,
            "database delete failed",
        ):
            manager.delete_conversation(
                conversation_id="conversation-abc",
                user_id="user-123",
            )

        store.delete_conversation.assert_called_once_with(
            "user-123",
            "conversation-abc",
        )

    def test_rehydration_uses_logical_conversation_id(self):
        store = PanoramaStore(
            client=_ListGateway(),
            settings=_settings(),
        )

        conversations = store.list_conversations("user-123")
        selected_id = conversations[0]["id"]

        # The identifier exposed to Telegram must be exactly the same
        # logical conversationId used by message persistence/retrieval.
        self.assertEqual(
            selected_id,
            "conversation-abc",
        )


if __name__ == "__main__":
    unittest.main()
