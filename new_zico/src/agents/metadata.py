from __future__ import annotations

from typing import Any, Dict

from src.agents.swap.storage import SwapStateRepository
from src.agents.dca.storage import DcaStateRepository
from src.agents.lending.storage import LendingStateRepository
from src.agents.staking.storage import StakingStateRepository


class Metadata:
    def __init__(self):
        self.crypto_data_agent: Dict[str, Any] = {}
        self._swap_repo = SwapStateRepository.instance()
        self._dca_repo = DcaStateRepository.instance()
        self._lending_repo = LendingStateRepository.instance()
        self._staking_repo = StakingStateRepository.instance()

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

    def get_dca_agent(self, user_id: str | None = None, conversation_id: str | None = None):
        try:
            return self._dca_repo.get_metadata(user_id, conversation_id)
        except ValueError:
            return {}

    def set_dca_agent(
        self,
        dca_agent: Dict[str, Any] | None,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ):
        try:
            if dca_agent:
                self._dca_repo.set_metadata(user_id, conversation_id, dca_agent)
            else:
                self._dca_repo.clear_metadata(user_id, conversation_id)
        except ValueError:
            return

    def clear_dca_agent(self, user_id: str | None = None, conversation_id: str | None = None) -> None:
        try:
            self._dca_repo.clear_metadata(user_id, conversation_id)
        except ValueError:
            return

    def get_dca_history(
        self,
        user_id: str | None = None,
        conversation_id: str | None = None,
        limit: int | None = None,
    ):
        try:
            return self._dca_repo.get_history(user_id, conversation_id, limit)
        except ValueError:
            return []

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

    def get_lending_agent(self, user_id: str | None = None, conversation_id: str | None = None):
        try:
            return self._lending_repo.get_metadata(user_id, conversation_id)
        except ValueError:
            return {}

    def set_lending_agent(
        self,
        lending_agent: Dict[str, Any] | None,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ):
        try:
            if lending_agent:
                self._lending_repo.set_metadata(user_id, conversation_id, lending_agent)
            else:
                self._lending_repo.clear_metadata(user_id, conversation_id)
        except ValueError:
            return

    def clear_lending_agent(self, user_id: str | None = None, conversation_id: str | None = None) -> None:
        try:
            self._lending_repo.clear_metadata(user_id, conversation_id)
        except ValueError:
            return

    def get_lending_history(
        self,
        user_id: str | None = None,
        conversation_id: str | None = None,
        limit: int | None = None,
    ):
        try:
            return self._lending_repo.get_history(user_id, conversation_id, limit)
        except ValueError:
            return []

    def get_staking_agent(self, user_id: str | None = None, conversation_id: str | None = None):
        try:
            return self._staking_repo.get_metadata(user_id, conversation_id)
        except ValueError:
            return {}

    def set_staking_agent(
        self,
        staking_agent: Dict[str, Any] | None,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ):
        try:
            if staking_agent:
                self._staking_repo.set_metadata(user_id, conversation_id, staking_agent)
            else:
                self._staking_repo.clear_metadata(user_id, conversation_id)
        except ValueError:
            return

    def clear_staking_agent(self, user_id: str | None = None, conversation_id: str | None = None) -> None:
        try:
            self._staking_repo.clear_metadata(user_id, conversation_id)
        except ValueError:
            return

    def get_staking_history(
        self,
        user_id: str | None = None,
        conversation_id: str | None = None,
        limit: int | None = None,
    ):
        try:
            return self._staking_repo.get_history(user_id, conversation_id, limit)
        except ValueError:
            return []


metadata = Metadata()
