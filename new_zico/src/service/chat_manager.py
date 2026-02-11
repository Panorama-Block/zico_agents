from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Optional

from src.models.chatMessage import AgentResponse, ChatMessage
from src.service.panorama_store import PanoramaStore

logger = logging.getLogger(__name__)


class ChatManager:
    """Facade that delegates chat persistence to the Panorama data gateway."""

    def __init__(self, store: PanoramaStore | None = None) -> None:
        self._store = store or PanoramaStore()

    @staticmethod
    def _resolve_ids(
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> tuple[str, str]:
        return (conversation_id or "default", user_id or "anonymous")

    # ---- Message access ---------------------------------------------------
    def get_messages(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        conversation_id, user_id = self._resolve_ids(conversation_id, user_id)
        self._store.ensure_conversation(user_id, conversation_id)
        messages = self._store.list_messages(user_id, conversation_id)
        return messages

    def get_last_message(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, str]:
        messages = self.get_messages(conversation_id, user_id)
        return messages[-1] if messages else {}

    def get_chat_history(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        messages = self.get_messages(conversation_id, user_id)
        return "\n".join(f"{msg.get('role')}: {msg.get('content')}" for msg in messages)

    # ---- Mutations --------------------------------------------------------
    def add_message(
        self,
        message: Dict[str, str],
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, str]:
        conversation_id, user_id = self._resolve_ids(conversation_id, user_id)
        self._store.ensure_user_and_conversation(user_id, conversation_id)
        chat_message = ChatMessage(**message)
        if not chat_message.message_id:
            chat_message.message_id = str(uuid.uuid4())
        chat_message.conversation_id = conversation_id
        chat_message.user_id = user_id
        stored = self._store.add_message(user_id, conversation_id, chat_message)
        logger.info(
            "Persisted message for user=%s conversation=%s role=%s",
            user_id,
            conversation_id,
            chat_message.role,
        )
        return stored

    def add_response(
        self,
        response: Dict[str, str],
        agent_name: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, str]:
        agent_response = AgentResponse(**response)
        chat_message = ChatMessage(
            role="assistant",
            content=agent_response.content,
            agent_name=agent_response.agent_name,
            agent_type=agent_response.agent_type,
            metadata=agent_response.metadata,
            timestamp=agent_response.timestamp,
            tool_results=agent_response.tool_results,
            next_agent=agent_response.next_agent,
            requires_followup=agent_response.requires_followup,
            status="completed" if agent_response.success else "failed",
            error_message=agent_response.error_message,
        )
        stored = self.add_message(
            chat_message.dict(),
            conversation_id=conversation_id,
            user_id=user_id,
        )
        logger.info(
            "Persisted agent response from %s for user=%s conversation=%s",
            agent_name,
            user_id,
            conversation_id,
        )
        return stored

    def clear_messages(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        conversation_id, user_id = self._resolve_ids(conversation_id, user_id)
        self._store.ensure_conversation(user_id, conversation_id)
        self._store.reset_conversation(user_id, conversation_id)
        logger.info(
            "Cleared messages for user=%s conversation=%s",
            user_id,
            conversation_id,
        )

    def delete_conversation(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        conversation_id, user_id = self._resolve_ids(conversation_id, user_id)
        self._store.delete_conversation(user_id, conversation_id)
        logger.info(
            "Deleted conversation for user=%s conversation=%s",
            user_id,
            conversation_id,
        )

    def create_conversation(self, user_id: Optional[str] = None) -> str:
        user_id = (user_id or "anonymous")
        conversation_id = f"conversation-{uuid.uuid4().hex[:8]}"
        self._store.ensure_user_and_conversation(user_id, conversation_id)
        logger.info(
            "Created new conversation for user=%s conversation=%s",
            user_id,
            conversation_id,
        )
        return conversation_id

    # ---- Discovery helpers ------------------------------------------------
    def get_all_conversation_ids(self, user_id: Optional[str] = None) -> List[str]:
        user_id = (user_id or "anonymous")
        conversations = self._store.list_conversations(user_id)
        return [c["id"] for c in conversations if isinstance(c, dict) and c.get("id")]

    def get_all_user_ids(self) -> List[str]:
        return self._store.list_users()

    def ensure_session(
        self,
        user_id: str,
        conversation_id: str,
        *,
        wallet_address: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> None:
        self._store.ensure_user_and_conversation(
            user_id,
            conversation_id,
            wallet_address=wallet_address,
            display_name=display_name,
        )

    # ---- Cost tracking ----------------------------------------------------
    def update_conversation_costs(
        self,
        cost_delta: Dict,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        Update the conversation with cost data from the latest request.

        Args:
            cost_delta: Cost delta dict with 'cost', 'tokens', 'calls' keys
            conversation_id: Conversation ID
            user_id: User ID

        Returns:
            Updated conversation data
        """
        conversation_id, user_id = self._resolve_ids(conversation_id, user_id)
        try:
            result = self._store.update_conversation_costs(user_id, conversation_id, cost_delta)
            logger.info(
                "Updated costs for user=%s conversation=%s: +$%.6f (%d calls)",
                user_id,
                conversation_id,
                cost_delta.get("cost", 0),
                cost_delta.get("calls", 0),
            )
            return result
        except Exception as exc:
            logger.warning(
                "Failed to update costs for user=%s conversation=%s: %s",
                user_id,
                conversation_id,
                exc,
            )
            return {}

    def get_conversation_costs(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        Get the accumulated costs for a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID

        Returns:
            Cost data dict
        """
        conversation_id, user_id = self._resolve_ids(conversation_id, user_id)
        return self._store.get_conversation_costs(user_id, conversation_id)


# Singleton-style accessor for the FastAPI routes
chat_manager_instance = ChatManager()
