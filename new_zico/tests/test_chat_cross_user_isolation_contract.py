import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call

from src.service.panorama_store import PanoramaStore


ALICE = "0xalice"
BOB = "0xbob"
CONVERSATION = "conversation-shared"


def _settings():
    return SimpleNamespace(
        tenant_id="test-tenant",
    )


class ChatCrossUserIsolationContractTest(unittest.TestCase):
    def test_message_history_is_scoped_by_user_and_conversation(self):
        client = MagicMock()
        client.list.return_value = {"data": []}
        store = PanoramaStore(client=client, settings=_settings())

        store.list_messages(ALICE, CONVERSATION)
        store.list_messages(BOB, CONVERSATION)

        self.assertEqual(
            client.list.call_args_list,
            [
                call(
                    "messages",
                    {
                        "where": {
                            "userId": ALICE,
                            "conversationId": CONVERSATION,
                        },
                        "orderBy": {"timestamp": "asc"},
                    },
                ),
                call(
                    "messages",
                    {
                        "where": {
                            "userId": BOB,
                            "conversationId": CONVERSATION,
                        },
                        "orderBy": {"timestamp": "asc"},
                    },
                ),
            ],
        )

    def test_conversation_listing_is_scoped_by_user(self):
        client = MagicMock()
        client.list.return_value = {"data": []}
        store = PanoramaStore(client=client, settings=_settings())

        store.list_conversations(ALICE)
        store.list_conversations(BOB)

        self.assertEqual(
            client.list.call_args_list,
            [
                call(
                    "conversations",
                    {
                        "where": {"userId": ALICE},
                        "orderBy": {"updatedAt": "desc"},
                    },
                ),
                call(
                    "conversations",
                    {
                        "where": {"userId": BOB},
                        "orderBy": {"updatedAt": "desc"},
                    },
                ),
            ],
        )

    def test_title_update_uses_structured_owner_identifier(self):
        client = MagicMock()
        store = PanoramaStore(client=client, settings=_settings())

        store.update_conversation_title(
            ALICE,
            CONVERSATION,
            "Alice title",
        )

        client.update.assert_called_once()
        entity, identifier, payload = client.update.call_args.args

        self.assertEqual(entity, "conversations")
        self.assertEqual(
            identifier,
            {
                "userId": ALICE,
                "conversationId": CONVERSATION,
            },
        )
        self.assertEqual(payload["title"], "Alice title")

        self.assertNotEqual(
            identifier,
            {
                "userId": BOB,
                "conversationId": CONVERSATION,
            },
        )

    def test_ensure_conversation_lookup_uses_structured_owner_identifier(self):
        client = MagicMock()
        client.get.return_value = {
            "userId": ALICE,
            "conversationId": CONVERSATION,
        }
        store = PanoramaStore(client=client, settings=_settings())

        result = store.ensure_conversation(
            ALICE,
            CONVERSATION,
        )

        self.assertEqual(
            result,
            {
                "userId": ALICE,
                "conversationId": CONVERSATION,
            },
        )
        client.get.assert_called_once_with(
            "conversations",
            {
                "userId": ALICE,
                "conversationId": CONVERSATION,
            },
        )
        client.create.assert_not_called()

    def test_same_conversation_id_for_two_users_produces_distinct_lookups(self):
        client = MagicMock()
        client.get.side_effect = [
            {
                "userId": ALICE,
                "conversationId": CONVERSATION,
            },
            {
                "userId": BOB,
                "conversationId": CONVERSATION,
            },
        ]
        store = PanoramaStore(client=client, settings=_settings())

        alice = store.ensure_conversation(ALICE, CONVERSATION)
        bob = store.ensure_conversation(BOB, CONVERSATION)

        self.assertEqual(alice["userId"], ALICE)
        self.assertEqual(bob["userId"], BOB)

        self.assertEqual(
            client.get.call_args_list,
            [
                call(
                    "conversations",
                    {
                        "userId": ALICE,
                        "conversationId": CONVERSATION,
                    },
                ),
                call(
                    "conversations",
                    {
                        "userId": BOB,
                        "conversationId": CONVERSATION,
                    },
                ),
            ],
        )

    def test_delete_reads_messages_only_from_authenticated_owner_scope(self):
        client = MagicMock()
        client.list.return_value = {"data": []}
        store = PanoramaStore(client=client, settings=_settings())

        store.delete_conversation(
            ALICE,
            CONVERSATION,
        )

        client.list.assert_called_once_with(
            "messages",
            {
                "where": {
                    "userId": ALICE,
                    "conversationId": CONVERSATION,
                },
                "orderBy": {"timestamp": "asc"},
            },
        )

        client.transact.assert_called_once()

        operations = client.transact.call_args.args[0]

        self.assertEqual(
            operations,
            [
                {
                    "op": "delete",
                    "entity": "conversations",
                    "args": {
                        "id": {
                            "userId": ALICE,
                            "conversationId": CONVERSATION,
                        }
                    },
                }
            ],
        )

        client.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
