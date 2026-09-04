import asyncio
import unittest
from unittest.mock import MagicMock, patch

from src.routes import chat_manager_routes
from src.security.chat_auth import PanoramaPrincipal
from src.service.chat_manager import ChatManager


ALICE = PanoramaPrincipal(user_id="0xalice")


class TruthfulDeletionContractTests(unittest.TestCase):
    def test_manager_propagates_durable_delete_failure(self):
        store = MagicMock()
        store.delete_conversation.side_effect = RuntimeError(
            "database delete failed"
        )

        manager = ChatManager(store=store)

        with self.assertRaisesRegex(
            RuntimeError,
            "database delete failed",
        ):
            manager.delete_conversation(
                conversation_id="conversation-abc",
                user_id=ALICE.user_id,
            )

        store.delete_conversation.assert_called_once_with(
            ALICE.user_id,
            "conversation-abc",
        )

    def test_route_does_not_report_success_when_manager_delete_fails(self):
        with patch.object(
            chat_manager_routes.chat_manager_instance,
            "delete_conversation",
            side_effect=RuntimeError("database delete failed"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "database delete failed",
            ):
                asyncio.run(
                    chat_manager_routes.delete_conversation(
                        conversation_id="conversation-abc",
                        user_id_query="0xbob",
                        user_id_body={"user_id": "0xbob"},
                        principal=ALICE,
                    )
                )

    def test_route_still_uses_authenticated_owner_on_success(self):
        with patch.object(
            chat_manager_routes.chat_manager_instance,
            "delete_conversation",
            return_value=None,
        ) as delete_conversation:
            result = asyncio.run(
                chat_manager_routes.delete_conversation(
                    conversation_id="conversation-abc",
                    user_id_query="0xbob",
                    user_id_body={"user_id": "0xbob"},
                    principal=ALICE,
                )
            )

        self.assertEqual(
            result,
            {"response": "successfully deleted conversation"},
        )
        delete_conversation.assert_called_once_with(
            "conversation-abc",
            ALICE.user_id,
        )


if __name__ == "__main__":
    unittest.main()

def test_delete_conversation_uses_single_atomic_gateway_transaction():
    """Messages and conversation must be deleted in one gateway transaction."""
    from unittest.mock import MagicMock

    from src.service.panorama_store import PanoramaStore

    store = object.__new__(PanoramaStore)
    store._client = MagicMock()
    store._logger = MagicMock()

    store.list_messages = MagicMock(
        return_value=[
            {"messageId": "message-1"},
            {"messageId": "message-2"},
        ]
    )

    store.delete_conversation("user-123", "conversation-abc")

    store._client.transact.assert_called_once()

    operations = store._client.transact.call_args.args[0]

    assert operations == [
        {
            "op": "delete",
            "entity": "messages",
            "args": {"id": "message-1"},
        },
        {
            "op": "delete",
            "entity": "messages",
            "args": {"id": "message-2"},
        },
        {
            "op": "delete",
            "entity": "conversations",
            "args": {
                "id": {
                    "userId": "user-123",
                    "conversationId": "conversation-abc",
                }
            },
        },
    ]

    store._client.delete.assert_not_called()

def test_delete_missing_conversation_is_idempotent_success():
    """Deleting an already-absent conversation must not call the gateway transaction."""
    from unittest.mock import MagicMock

    from src.service.panorama_store import PanoramaStore

    store = object.__new__(PanoramaStore)
    store._client = MagicMock()
    store._logger = MagicMock()

    store._client.get.return_value = None
    store.list_messages = MagicMock(return_value=[])

    store.delete_conversation(
        "user-123",
        "conversation-missing",
    )

    store._client.get.assert_called_once_with(
        "conversations",
        {
            "userId": "user-123",
            "conversationId": "conversation-missing",
        },
    )

    store._client.transact.assert_not_called()
