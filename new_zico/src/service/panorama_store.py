from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.models.chatMessage import ChatMessage

from src.integrations.panorama_gateway import (
    PanoramaGatewayClient,
    PanoramaGatewayError,
    PanoramaGatewaySettings,
    get_panorama_settings,
)


DEFAULT_DISCLAIMER = (
    "This highly experimental chatbot is not intended for making important decisions. "
    "Its responses are generated using AI models and may not always be accurate. "
    "By using this chatbot, you acknowledge that you use it at your own discretion "
    "and assume all risks associated with its limitations and potential errors."
)


def _utc_now_iso() -> str:
    """Return an RFC3339 timestamp with millisecond precision and Z suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _normalize_datetime(value: Any | None) -> Optional[str]:
    """Convert datetime-like inputs to gateway-friendly RFC3339 strings."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    else:
        return value

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _conversation_key(user_id: str, conversation_id: str) -> str:
    return f"{user_id}:{conversation_id}"


def _drop_none(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys with None values so the gateway never receives JSON null."""
    return {key: value for key, value in data.items() if value is not None}


class PanoramaStore:
    """Bridges chat persistence to the Panorama data gateway."""

    def __init__(
        self,
        *,
        client: PanoramaGatewayClient | None = None,
        settings: PanoramaGatewaySettings | None = None,
    ) -> None:
        self._settings = settings or get_panorama_settings()
        self._client = client or PanoramaGatewayClient(self._settings)
        self._logger = logging.getLogger(__name__)

    # ---- user helpers -----------------------------------------------------
    def ensure_user(
        self,
        user_id: str,
        *,
        wallet_address: Optional[str] = None,
        display_name: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            user = self._client.get("users", user_id)
        except PanoramaGatewayError as exc:
            if exc.status_code != 404:
                raise
            user = None

        if user:
            # Update last seen without failing the request if the patch raises.
            try:
                payload: Dict[str, Any] = {"lastSeenAt": _utc_now_iso()}
                if display_name:
                    payload["displayName"] = display_name
                if wallet_address:
                    payload["walletAddress"] = wallet_address
                if attributes:
                    payload["attributes"] = attributes
                self._client.update("users", user_id, payload)
            except PanoramaGatewayError:
                pass
            return user

        payload = _drop_none(
            {
                "userId": user_id,
                "walletAddress": wallet_address,
                "displayName": display_name,
                "attributes": attributes or {},
                "tenantId": self._settings.tenant_id,
                "createdAt": _utc_now_iso(),
                "lastSeenAt": _utc_now_iso(),
            }
        )
        try:
            return self._client.create("users", payload)
        except PanoramaGatewayError as exc:
            self._logger.error(
                "Failed to create user %s via gateway: status=%s payload=%s request=%s",
                user_id,
                exc.status_code,
                exc.payload,
                payload,
            )
            raise

    # ---- conversation helpers ---------------------------------------------
    def ensure_conversation(
        self,
        user_id: str,
        conversation_id: str,
        *,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        conv_key = _conversation_key(user_id, conversation_id)
        try:
            conversation = self._client.get("conversations", conv_key)
        except PanoramaGatewayError as exc:
            if exc.status_code != 404:
                raise
            conversation = None

        if conversation:
            return conversation

        payload = _drop_none(
            {
                "id": conv_key,
                "userId": user_id,
                "conversationId": conversation_id,
                "title": title,
                "status": "active",
                "messageCount": 0,
                "tenantId": self._settings.tenant_id,
                "contextState": {},
                "memoryState": {},
                "createdAt": _utc_now_iso(),
                "updatedAt": _utc_now_iso(),
            }
        )
        try:
            conversation = self._client.create("conversations", payload)
        except PanoramaGatewayError as exc:
            self._logger.error(
                "Failed to create conversation %s for user %s: status=%s payload=%s request=%s",
                conversation_id,
                user_id,
                exc.status_code,
                exc.payload,
                payload,
            )
            raise
        self._create_disclaimer_message(user_id, conversation_id)
        return conversation

    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        result = self._client.list(
            "conversations",
            {
                "where": {"userId": user_id},
                "orderBy": {"updatedAt": "desc"},
            },
        )
        data = result.get("data", []) if isinstance(result, dict) else []
        return [
            {
                "id": item.get("conversationId"),
                "title": item.get("title"),
                "updated_at": item.get("updatedAt"),
            }
            for item in data
            if item.get("conversationId")
        ]

    def list_users(self, limit: int = 1000) -> List[str]:
        result = self._client.list(
            "users",
            {
                "orderBy": {"createdAt": "desc"},
                "take": limit,
            },
        )
        data = result.get("data", []) if isinstance(result, dict) else []
        return [item.get("userId") for item in data if item.get("userId")]

    def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        messages = self.list_messages(user_id, conversation_id)
        deletes: List[Dict[str, Any]] = [
            {
                "op": "delete",
                "entity": "messages",
                "args": {"id": message["messageId"]},
            }
            for message in messages
            if message.get("messageId")
        ]
        if deletes:
            self._client.transact(deletes)

        conv_key = _conversation_key(user_id, conversation_id)
        try:
            self._client.delete("conversations", conv_key)
        except PanoramaGatewayError as exc:
            if exc.status_code != 404:
                raise

    def reset_conversation(self, user_id: str, conversation_id: str) -> None:
        messages = self.list_messages(user_id, conversation_id)
        deletes = [
            {
                "op": "delete",
                "entity": "messages",
                "args": {"id": message["messageId"]},
            }
            for message in messages
            if message.get("messageId")
        ]
        if deletes:
            self._client.transact(deletes)

        conv_key = _conversation_key(user_id, conversation_id)
        self._client.update(
            "conversations",
            conv_key,
            {"messageCount": 0, "updatedAt": _utc_now_iso()},
        )
        self._create_disclaimer_message(user_id, conversation_id)

    # ---- message helpers ---------------------------------------------------
    def list_messages(self, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        result = self._client.list(
            "messages",
            {
                "where": {"userId": user_id, "conversationId": conversation_id},
                "orderBy": {"timestamp": "asc"},
            },
        )
        if isinstance(result, dict):
            messages = result.get("data", [])
            self._logger.info(f"Fetched {len(messages)} messages for conv {conversation_id}. Sample metadata: {messages[0].get('metadata') if messages else 'N/A'}")
            return messages
        return []

    def add_message(
        self,
        user_id: str,
        conversation_id: str,
        message: ChatMessage,
    ) -> Dict[str, Any]:
        conversation = self.ensure_conversation(user_id, conversation_id)
        message_dict = message.dict()
        message_id = message_dict.get("message_id") or message_dict.get("messageId")
        if not message_id:
            message_id = str(uuid.uuid4())
        
        # DEBUG: Log incoming metadata before persistence
        input_metadata = message_dict.get("metadata") or {}
        self._logger.info(f"Persisting message {message_id} with metadata keys: {list(input_metadata.keys())} Event: {input_metadata.get('event')}")
        
        timestamp = _normalize_datetime(message_dict.get("timestamp")) or _utc_now_iso()
        message_payload = _drop_none(
            {
                "messageId": message_id,
                "userId": user_id,
                "conversationId": conversation_id,
                "role": message_dict.get("role"),
                "content": message_dict.get("content"),
                "agentName": message_dict.get("agent_name"),
                "agentType": message_dict.get("agent_type"),
                "requiresAction": message_dict.get("requires_action", False),
                "actionType": message_dict.get("action_type"),
                "metadata": message_dict.get("metadata") or {},
                "status": message_dict.get("status"),
                "errorMessage": message_dict.get("error_message"),
                "toolCalls": message_dict.get("tool_calls"),
                "toolResults": message_dict.get("tool_results"),
                "nextAgent": message_dict.get("next_agent"),
                "requiresFollowup": message_dict.get("requires_followup", False),
                "timestamp": timestamp,
                "tenantId": self._settings.tenant_id,
            }
        )

        # Prepare updates
        conversation_updates = {
            "lastMessageId": message_payload["messageId"],
            "messageCount": (conversation.get("messageCount") or 0) + 1,
            "updatedAt": _utc_now_iso(),
        }

        # Auto-generate title for new conversations based on first user message
        if (
            message_payload["role"] == "user"
            and (not conversation.get("title") or conversation.get("title") == "New Chat")
        ):
            # Simple truncation for title
            content = message_payload.get("content", "")
            generated_title = (content[:47] + "...") if len(content) > 50 else content
            conversation_updates["title"] = generated_title

        operations = [
            {"op": "create", "entity": "messages", "args": {"data": message_payload}},
            {
                "op": "update",
                "entity": "conversations",
                "args": {
                    "id": conversation["id"],
                    "data": conversation_updates,
                },
            },
        ]
        self._client.transact(operations)

        memory_payload = _drop_none(
            {
                "messageId": message_payload["messageId"],
                "role": message_payload["role"],
                "content": message_payload["content"],
                "agentName": message_payload.get("agentName"),
                "agentType": message_payload.get("agentType"),
                "metadata": message_payload.get("metadata"),
                "requiresAction": message_payload.get("requiresAction"),
                "timestamp": message_payload.get("timestamp"),
            }
        )
        try:
            self.create_conversation_memory(
                user_id,
                conversation_id,
                scope="conversation",
                memory_type=message_payload["role"],
                payload=memory_payload,
            )
        except PanoramaGatewayError:
            # Memory writes should never block the main chat flow.
            pass

        return message_payload

    def _create_disclaimer_message(self, user_id: str, conversation_id: str) -> None:
        disclaimer = ChatMessage(
            role="assistant",
            content=DEFAULT_DISCLAIMER,
            metadata={},
            user_id=user_id,
            conversation_id=conversation_id,
        )
        self.add_message(user_id, conversation_id, disclaimer)

    # ---- conversation memory ----------------------------------------------
    def create_conversation_memory(
        self,
        user_id: str,
        conversation_id: Optional[str],
        scope: str,
        memory_type: str,
        payload: Dict[str, Any],
        *,
        label: Optional[str] = None,
        importance_score: Optional[float] = None,
        expires_at: Optional[Any] = None,
    ) -> Dict[str, Any]:
        memory_payload = _drop_none(
            {
                "userId": user_id,
                "conversationId": conversation_id,
                "scope": scope,
                "memoryType": memory_type,
                "payload": payload,
                "tenantId": self._settings.tenant_id,
                "label": label,
                "importanceScore": importance_score,
                "expiresAt": _normalize_datetime(expires_at),
                "createdAt": _utc_now_iso(),
                "updatedAt": _utc_now_iso(),
            }
        )
        return self._client.create("conversation-memories", memory_payload)

    # ---- utility -----------------------------------------------------------
    def ensure_user_and_conversation(
        self,
        user_id: str,
        conversation_id: str,
        *,
        wallet_address: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        user = self.ensure_user(
            user_id,
            wallet_address=wallet_address,
            display_name=display_name,
        )
        conversation = self.ensure_conversation(user_id, conversation_id)
        return user, conversation

    # ---- cost tracking -----------------------------------------------------
    def update_conversation_costs(
        self,
        user_id: str,
        conversation_id: str,
        cost_delta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update the conversation with accumulated cost data.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            cost_delta: Cost delta from this request (cost, tokens, calls)

        Returns:
            Updated conversation data
        """
        conv_key = _conversation_key(user_id, conversation_id)
        try:
            conversation = self._client.get("conversations", conv_key)
        except PanoramaGatewayError as exc:
            if exc.status_code == 404:
                self._logger.warning("Conversation %s not found for cost update", conv_key)
                return {}
            raise

        # Get existing cost data from contextState
        context_state = conversation.get("contextState", {}) or {}
        existing_costs = context_state.get("costs", {
            "total_cost": 0.0,
            "total_tokens": {"input": 0, "output": 0, "cache": 0},
            "total_calls": 0,
        })

        # Accumulate costs
        delta_tokens = cost_delta.get("tokens", {})
        existing_tokens = existing_costs.get("total_tokens", {"input": 0, "output": 0, "cache": 0})

        updated_costs = {
            "total_cost": round(existing_costs.get("total_cost", 0.0) + cost_delta.get("cost", 0.0), 6),
            "total_tokens": {
                "input": existing_tokens.get("input", 0) + delta_tokens.get("input", 0),
                "output": existing_tokens.get("output", 0) + delta_tokens.get("output", 0),
                "cache": existing_tokens.get("cache", 0) + delta_tokens.get("cache", 0),
            },
            "total_calls": existing_costs.get("total_calls", 0) + cost_delta.get("calls", 0),
            "last_updated": _utc_now_iso(),
        }

        # Update contextState with new costs
        context_state["costs"] = updated_costs
        try:
            return self._client.update(
                "conversations",
                conv_key,
                {"contextState": context_state, "updatedAt": _utc_now_iso()},
            )
        except PanoramaGatewayError as exc:
            self._logger.error(
                "Failed to update costs for conversation %s: status=%s",
                conv_key,
                exc.status_code,
            )
            raise

    def get_conversation_costs(
        self,
        user_id: str,
        conversation_id: str,
    ) -> Dict[str, Any]:
        """
        Get the accumulated costs for a conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            Cost data or empty dict if not found
        """
        conv_key = _conversation_key(user_id, conversation_id)
        try:
            conversation = self._client.get("conversations", conv_key)
        except PanoramaGatewayError as exc:
            if exc.status_code == 404:
                return {}
            raise

        context_state = conversation.get("contextState", {}) or {}
        return context_state.get("costs", {
            "total_cost": 0.0,
            "total_tokens": {"input": 0, "output": 0, "cache": 0},
            "total_calls": 0,
        })