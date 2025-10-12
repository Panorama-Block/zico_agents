from __future__ import annotations

from typing import Any, Dict

from src.agents.swap.storage import SwapStateRepository


class Metadata:
    def __init__(self):
        self.crypto_data_agent: Dict[str, Any] = {}
        self._swap_repo = SwapStateRepository.instance()

    def get_crypto_data_agent(self):
        return self.crypto_data_agent

    def set_crypto_data_agent(self, crypto_data_agent):
        self.crypto_data_agent = crypto_data_agent

    def get_swap_agent(self, user_id: str | None = None, conversation_id: str | None = None):
        try:
            return self._swap_repo.get_metadata(user_id, conversation_id)
        except ValueError:
            return {}

    def set_swap_agent(
        self,
        swap_agent: Dict[str, Any] | None,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ):
        try:
            if swap_agent:
                self._swap_repo.set_metadata(user_id, conversation_id, swap_agent)
            else:
                self._swap_repo.clear_metadata(user_id, conversation_id)
        except ValueError:
            # Ignore clears when identity is missing; no actionable state to update.
            return

    def get_swap_history(
        self,
        user_id: str | None = None,
        conversation_id: str | None = None,
        limit: int | None = None,
    ):
        try:
            return self._swap_repo.get_history(user_id, conversation_id, limit)
        except ValueError:
            return []


metadata = Metadata()
