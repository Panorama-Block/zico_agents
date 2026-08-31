from __future__ import annotations

from typing import Any, Dict, List

from src.integrations.panorama_gateway import PanoramaGatewayError
from src.service.panorama_store import PanoramaStore, _conversation_identifier, _utc_now_iso


class ChatPersistenceStore(PanoramaStore):
    """Chat-specific storage contract over the generic Panorama data gateway.

    The gateway exposes conversations by a composite resource identifier
    (userId + conversationId). The public chat API must expose only the domain
    conversationId. This adapter keeps that gateway identifier internal and
    makes read/delete operations non-destructive and durable.
    """

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
                "id": item["conversationId"],
                "conversation_id": item["conversationId"],
                "title": item.get("title"),
                "updated_at": item.get("updatedAt"),
                "message_count": item.get("messageCount"),
            }
            for item in data
            if isinstance(item, dict) and item.get("conversationId")
        ]

    def conversation_exists(self, user_id: str, conversation_id: str) -> bool:
        try:
            self._client.get(
                "conversations",
                _conversation_identifier(user_id, conversation_id),
            )
            return True
        except PanoramaGatewayError as exc:
            if exc.status_code == 404:
                return False
            raise

    def _list_entity(self, entity: str, where: Dict[str, Any]) -> List[Dict[str, Any]]:
        result = self._client.list(entity, {"where": where})
        if isinstance(result, dict) and isinstance(result.get("data"), list):
            return [item for item in result["data"] if isinstance(item, dict)]
        return []

    def _message_delete_operations(self, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        operations: List[Dict[str, Any]] = []
        messages = self.list_messages(user_id, conversation_id)

        # MessageToolCall has a restrictive FK to Message in the current DB
        # schema, so tool calls must be removed before messages.
        for message in messages:
            message_id = message.get("messageId")
            if not message_id:
                continue
            for tool_call in self._list_entity("message-tool-calls", {"messageId": message_id}):
                tool_call_id = tool_call.get("toolCallId")
                if tool_call_id:
                    operations.append(
                        {
                            "op": "delete",
                            "entity": "message-tool-calls",
                            "args": {"id": tool_call_id},
                        }
                    )

        for message in messages:
            message_id = message.get("messageId")
            if message_id:
                operations.append(
                    {
                        "op": "delete",
                        "entity": "messages",
                        "args": {"id": message_id},
                    }
                )
        return operations

    def _conversation_state_delete_operations(self, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        operations: List[Dict[str, Any]] = []

        # Conversation memories are part of the deleted chat state.
        for memory in self._list_entity(
            "conversation-memories",
            {"userId": user_id, "conversationId": conversation_id},
        ):
            memory_id = memory.get("memoryId")
            if memory_id:
                operations.append(
                    {
                        "op": "delete",
                        "entity": "conversation-memories",
                        "args": {"id": memory_id},
                    }
                )

        # Ephemeral agent/session state must not survive a deleted chat. Audit
        # histories/turns are intentionally retained.
        for shared_state in self._list_entity(
            "agent-shared-states",
            {"userId": user_id, "conversationId": conversation_id},
        ):
            agent_name = shared_state.get("agentName")
            if agent_name:
                operations.append(
                    {
                        "op": "delete",
                        "entity": "agent-shared-states",
                        "args": {
                            "id": {
                                "agentName": agent_name,
                                "userId": user_id,
                                "conversationId": conversation_id,
                            }
                        },
                    }
                )

        for entity in ("swap-sessions", "dca-sessions"):
            for _record in self._list_entity(
                entity,
                {"userId": user_id, "conversationId": conversation_id},
            ):
                operations.append(
                    {
                        "op": "delete",
                        "entity": entity,
                        "args": {
                            "id": {
                                "userId": user_id,
                                "conversationId": conversation_id,
                            }
                        },
                    }
                )
                break

        return operations

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        if not self.conversation_exists(user_id, conversation_id):
            return False

        operations = self._message_delete_operations(user_id, conversation_id)
        operations.extend(self._conversation_state_delete_operations(user_id, conversation_id))
        if operations:
            self._client.transact(operations)

        self._logger.info(
            "conversation.delete user_id=%s conversation_id=%s identifier_type=structured",
            user_id,
            conversation_id,
        )
        self._client.delete(
            "conversations",
            _conversation_identifier(user_id, conversation_id),
        )
        return True

    def reset_conversation(self, user_id: str, conversation_id: str) -> None:
        if not self.conversation_exists(user_id, conversation_id):
            raise PanoramaGatewayError("Conversation not found", 404)

        operations = self._message_delete_operations(user_id, conversation_id)
        if operations:
            self._client.transact(operations)

        self._client.update(
            "conversations",
            _conversation_identifier(user_id, conversation_id),
            {
                "messageCount": 0,
                "lastMessageId": "",
                "updatedAt": _utc_now_iso(),
            },
        )
        self._create_disclaimer_message(user_id, conversation_id)
