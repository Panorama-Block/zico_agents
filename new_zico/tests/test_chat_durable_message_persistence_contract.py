import ast
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.models.chatMessage import ChatMessage
from src.service.panorama_store import PanoramaStore


APP_PATH = Path(__file__).resolve().parents[1] / "src" / "app.py"

USER_ID = "0xalice"
CONVERSATION_ID = "conversation-durable"


def _settings():
    return SimpleNamespace(
        tenant_id="test-tenant",
    )


def _load_app_tree():
    return ast.parse(APP_PATH.read_text())


def _function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node
    raise AssertionError(f"Function {name!r} not found")


def _source_segment(node):
    source = APP_PATH.read_text()
    segment = ast.get_source_segment(source, node)
    if segment is None:
        raise AssertionError(f"Could not read source for {node.name}")
    return segment


class DurablePanoramaStoreContractTest(unittest.TestCase):
    def test_user_message_transaction_contains_message_and_conversation_update(self):
        client = MagicMock()
        client.get.return_value = {
            "userId": USER_ID,
            "conversationId": CONVERSATION_ID,
            "messageCount": 0,
            "title": None,
        }

        store = PanoramaStore(
            client=client,
            settings=_settings(),
        )

        message = ChatMessage(
            role="user",
            content="Persist this message",
        )

        stored = store.add_message(
            USER_ID,
            CONVERSATION_ID,
            message,
        )

        client.transact.assert_called_once()
        operations = client.transact.call_args.args[0]

        self.assertEqual(len(operations), 2)

        create_operation = operations[0]
        update_operation = operations[1]

        self.assertEqual(create_operation["op"], "create")
        self.assertEqual(create_operation["entity"], "messages")

        persisted_message = create_operation["args"]["data"]

        self.assertEqual(persisted_message["userId"], USER_ID)
        self.assertEqual(
            persisted_message["conversationId"],
            CONVERSATION_ID,
        )
        self.assertEqual(persisted_message["role"], "user")
        self.assertEqual(
            persisted_message["content"],
            "Persist this message",
        )

        self.assertEqual(update_operation["op"], "update")
        self.assertEqual(
            update_operation["entity"],
            "conversations",
        )
        self.assertEqual(
            update_operation["args"]["id"],
            {
                "userId": USER_ID,
                "conversationId": CONVERSATION_ID,
            },
        )

        conversation_update = update_operation["args"]["data"]

        self.assertEqual(
            conversation_update["lastMessageId"],
            persisted_message["messageId"],
        )
        self.assertEqual(
            conversation_update["messageCount"],
            1,
        )

        self.assertEqual(
            stored["messageId"],
            persisted_message["messageId"],
        )

    def test_successive_messages_advance_conversation_metadata(self):
        client = MagicMock()

        client.get.side_effect = [
            {
                "userId": USER_ID,
                "conversationId": CONVERSATION_ID,
                "messageCount": 0,
                "title": None,
            },
            {
                "userId": USER_ID,
                "conversationId": CONVERSATION_ID,
                "messageCount": 1,
                "title": "First message",
            },
        ]

        store = PanoramaStore(
            client=client,
            settings=_settings(),
        )

        first = store.add_message(
            USER_ID,
            CONVERSATION_ID,
            ChatMessage(
                role="user",
                content="First message",
            ),
        )

        second = store.add_message(
            USER_ID,
            CONVERSATION_ID,
            ChatMessage(
                role="assistant",
                content="Second message",
            ),
        )

        transact_calls = client.transact.call_args_list

        self.assertEqual(len(transact_calls), 2)

        first_ops = transact_calls[0].args[0]
        second_ops = transact_calls[1].args[0]

        self.assertEqual(
            first_ops[1]["args"]["data"]["messageCount"],
            1,
        )
        self.assertEqual(
            first_ops[1]["args"]["data"]["lastMessageId"],
            first["messageId"],
        )

        self.assertEqual(
            second_ops[1]["args"]["data"]["messageCount"],
            2,
        )
        self.assertEqual(
            second_ops[1]["args"]["data"]["lastMessageId"],
            second["messageId"],
        )

        self.assertEqual(
            second_ops[0]["args"]["data"]["userId"],
            USER_ID,
        )
        self.assertEqual(
            second_ops[0]["args"]["data"]["conversationId"],
            CONVERSATION_ID,
        )

    def test_history_read_returns_gateway_messages_in_timestamp_order(self):
        client = MagicMock()
        client.list.return_value = {
            "data": [
                {
                    "messageId": "m-user",
                    "userId": USER_ID,
                    "conversationId": CONVERSATION_ID,
                    "role": "user",
                    "content": "Question",
                },
                {
                    "messageId": "m-assistant",
                    "userId": USER_ID,
                    "conversationId": CONVERSATION_ID,
                    "role": "assistant",
                    "content": "Answer",
                },
            ]
        }

        store = PanoramaStore(
            client=client,
            settings=_settings(),
        )

        history = store.list_messages(
            USER_ID,
            CONVERSATION_ID,
        )

        client.list.assert_called_once_with(
            "messages",
            {
                "where": {
                    "userId": USER_ID,
                    "conversationId": CONVERSATION_ID,
                },
                "orderBy": {
                    "timestamp": "asc",
                },
            },
        )

        self.assertEqual(
            [message["role"] for message in history],
            ["user", "assistant"],
        )
        self.assertEqual(
            [message["content"] for message in history],
            ["Question", "Answer"],
        )


class StreamingDurabilityContractTest(unittest.TestCase):
    def test_stream_does_not_fire_and_forget_assistant_persistence(self):
        tree = _load_app_tree()
        function = _function(tree, "_build_event_generator")
        source = _source_segment(function)

        self.assertNotIn(
            "asyncio.create_task(",
            source,
            msg=(
                "Streaming completion must not fire-and-forget "
                "assistant persistence."
            ),
        )

    def test_stream_awaits_assistant_persistence_before_done_event(self):
        tree = _load_app_tree()
        function = _function(tree, "_build_event_generator")
        source = _source_segment(function)

        persist_position = source.find(
            "await _persist_response_bg("
        )
        done_position = source.find(
            'yield _sse("done"'
        )

        self.assertNotEqual(
            persist_position,
            -1,
            "Streaming path must await assistant persistence.",
        )
        self.assertNotEqual(
            done_position,
            -1,
            "Streaming path must emit a done event.",
        )
        self.assertLess(
            persist_position,
            done_position,
            (
                "Assistant persistence must complete before the "
                "stream acknowledges completion."
            ),
        )


if __name__ == "__main__":
    unittest.main()
