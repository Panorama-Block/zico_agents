import asyncio
import unittest
from unittest.mock import patch

from src.security.chat_auth import PanoramaPrincipal
from src.routes import chat_manager_routes


ALICE = PanoramaPrincipal(user_id="0xalice")
BOB = "0xbob"


class ChatRouteOwnershipContractTest(unittest.TestCase):
    def test_get_messages_uses_authenticated_principal_not_query_user(self):
        with patch.object(
            chat_manager_routes.chat_manager_instance,
            "get_messages",
            return_value=[],
        ) as get_messages:
            result = asyncio.run(
                chat_manager_routes.get_messages(
                    conversation_id="conversation-abc",
                    user_id=BOB,
                    principal=ALICE,
                )
            )

        self.assertEqual(result, {"messages": []})
        get_messages.assert_called_once_with(
            "conversation-abc",
            ALICE.user_id,
        )

    def test_list_conversations_uses_authenticated_principal_not_query_user(self):
        with patch.object(
            chat_manager_routes.chat_manager_instance,
            "get_conversations",
            return_value=[],
        ) as get_conversations:
            result = asyncio.run(
                chat_manager_routes.get_conversations(
                    user_id_query=BOB,
                    user_id_str=None,
                    principal=ALICE,
                )
            )

        self.assertEqual(result, {"conversations": []})
        get_conversations.assert_called_once_with(ALICE.user_id)

    def test_create_conversation_uses_authenticated_principal_not_body_user(self):
        with patch.object(
            chat_manager_routes.chat_manager_instance,
            "create_conversation",
            return_value="conversation-new",
        ) as create_conversation:
            result = asyncio.run(
                chat_manager_routes.create_conversation(
                    user_id_query=BOB,
                    body={"user_id": BOB},
                    principal=ALICE,
                )
            )

        self.assertEqual(
            result,
            {"conversation_id": "conversation-new"},
        )
        create_conversation.assert_called_once_with(ALICE.user_id)

    def test_delete_conversation_uses_authenticated_principal_not_query_user(self):
        with patch.object(
            chat_manager_routes.chat_manager_instance,
            "delete_conversation",
            return_value=None,
        ) as delete_conversation:
            result = asyncio.run(
                chat_manager_routes.delete_conversation(
                    conversation_id="conversation-abc",
                    user_id_query=BOB,
                    user_id_body={"user_id": BOB},
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

    def test_generate_title_uses_authenticated_principal_not_body_user(self):
        body = chat_manager_routes.GenerateTitleRequest(
            user_id=BOB,
            conversation_id="conversation-abc",
            message="Explain Avalanche settlement",
        )

        class FakeLLM:
            def invoke(self, prompt):
                class Result:
                    content = "Avalanche Settlement"
                return Result()

        with (
            patch.object(
                chat_manager_routes.Config,
                "get_llm",
                return_value=FakeLLM(),
            ),
            patch.object(
                chat_manager_routes.chat_manager_instance,
                "update_conversation_title",
                return_value=None,
            ) as update_title,
        ):
            result = asyncio.run(
                chat_manager_routes.generate_title(
                    body=body,
                    principal=ALICE,
                )
            )

        self.assertEqual(
            result,
            {"title": "Avalanche Settlement"},
        )
        update_title.assert_called_once_with(
            "conversation-abc",
            ALICE.user_id,
            title="Avalanche Settlement",
        )


if __name__ == "__main__":
    unittest.main()
