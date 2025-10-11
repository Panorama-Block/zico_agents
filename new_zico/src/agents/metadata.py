from __future__ import annotations

from typing import Any, Dict, Tuple


class Metadata:
    def __init__(self):
        self.crypto_data_agent: Dict[str, Any] = {}
        self._swap_agent: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def get_crypto_data_agent(self):
        return self.crypto_data_agent

    def set_crypto_data_agent(self, crypto_data_agent):
        self.crypto_data_agent = crypto_data_agent

    def _swap_key(self, user_id: str | None, conversation_id: str | None) -> Tuple[str, str]:
        user = user_id or "__default_swap_user__"
        conversation = conversation_id or "__default_swap_conversation__"
        return user, conversation

    def get_swap_agent(self, user_id: str | None = None, conversation_id: str | None = None):
        key = self._swap_key(user_id, conversation_id)
        return self._swap_agent.get(key, {})

    def set_swap_agent(
        self,
        swap_agent: Dict[str, Any] | None,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ):
        key = self._swap_key(user_id, conversation_id)
        if swap_agent:
            self._swap_agent[key] = swap_agent
        else:
            self._swap_agent.pop(key, None)


metadata = Metadata()
