import re
import unittest
from unittest.mock import MagicMock

from src.service.chat_manager import ChatManager


class ConversationIdContractTests(unittest.TestCase):
    def test_new_conversation_uses_full_uuid4_entropy(self):
        store = MagicMock()
        manager = ChatManager(store=store)

        conversation_id = manager.create_conversation(
            user_id="user-123"
        )

        self.assertRegex(
            conversation_id,
            r"^conversation-[0-9a-f]{32}$",
        )

        store.ensure_user_and_conversation.assert_called_once_with(
            "user-123",
            conversation_id,
        )

    def test_generated_conversation_ids_are_unique_and_full_length(self):
        store = MagicMock()
        manager = ChatManager(store=store)

        generated = {
            manager.create_conversation(user_id="user-123")
            for _ in range(256)
        }

        self.assertEqual(len(generated), 256)

        for conversation_id in generated:
            self.assertEqual(
                len(conversation_id),
                len("conversation-") + 32,
            )
            self.assertTrue(
                re.fullmatch(
                    r"conversation-[0-9a-f]{32}",
                    conversation_id,
                )
            )

    def test_existing_short_logical_ids_remain_accepted(self):
        store = MagicMock()
        manager = ChatManager(store=store)

        legacy_id = "conversation-4b48d75b"

        manager.get_messages(
            conversation_id=legacy_id,
            user_id="user-123",
        )

        store.list_messages.assert_called_once_with(
            "user-123",
            legacy_id,
        )


if __name__ == "__main__":
    unittest.main()
