import asyncio
import unittest
from unittest.mock import patch

from src.security.chat_auth import PanoramaPrincipal
from src.routes import chat_manager_routes


ALICE = PanoramaPrincipal(user_id="0xalice")


class ChatTitleLifecycleContractTest(unittest.TestCase):
    def test_generate_title_does_not_report_success_when_persistence_fails(self):
        body = chat_manager_routes.GenerateTitleRequest(
            user_id="0xignored-caller",
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
                side_effect=RuntimeError("durable title persistence failed"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                asyncio.run(
                    chat_manager_routes.generate_title(
                        body=body,
                        principal=ALICE,
                    )
                )


if __name__ == "__main__":
    unittest.main()
