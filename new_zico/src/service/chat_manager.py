import logging
import time
from typing import Dict, List, Optional
from src.models.chatMessage import ChatMessage, ConversationState, AgentResponse
from datetime import datetime

logger = logging.getLogger(__name__)


class ChatManager:
    """
    Manages chat conversations and message history.

    This class provides functionality to:
    - Create and manage multiple conversations identified by unique IDs
    - Associate conversations with specific users
    - Add/retrieve messages and responses within conversations
    - Clear conversation history
    - Get chat history in different formats
    - Delete conversations

    Each conversation starts with a default disclaimer message about the experimental nature
    of the chatbot.

    Attributes:
        user_conversations (Dict[str, Dict[str, ConversationState]]): Dictionary mapping user IDs to their conversations
        default_message (ChatMessage): Default disclaimer message added to new conversations

    Example:
        >>> chat_manager = ChatManager()
        >>> chat_manager.add_message({"role": "user", "content": "Hello"}, "conv1", "user123")
        >>> messages = chat_manager.get_messages("conv1", "user123")
    """

    def __init__(self) -> None:
        self.user_conversations: Dict[str, Dict[str, ConversationState]] = {}
        self.default_message = ChatMessage(
            role="assistant",
            content="""This highly experimental chatbot is not intended for making important decisions. Its
                        responses are generated using AI models and may not always be accurate.
                        By using this chatbot, you acknowledge that you use it at your own discretion
                        and assume all risks associated with its limitations and potential errors.""",
            metadata={},
        )

        # Backward compatibility - Initialize with default conversation for anonymous user
        self._initialize_user("anonymous")
        self.user_conversations["anonymous"]["default"] = ConversationState(
            conversation_id="default",
            user_id="anonymous",
            messages=[self.default_message],
            context={},
            memory={},
            agent_history=[],
            current_agent=None,
            last_message_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )

    def _get_conversation_id(self, conversation_id: Optional[str] = None) -> str:
        """Helper method to get conversation ID, defaulting to 'default' if None provided"""
        return conversation_id or "default"

    def _get_user_id(self, user_id: Optional[str] = None) -> str:
        """Helper method to get user ID, defaulting to 'anonymous' if None provided"""
        return user_id or "anonymous"

    def _initialize_user(self, user_id: str) -> None:
        """Initialize conversations dictionary for a new user"""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = {}
            logger.info(f"Initialized conversations for user {user_id}")

    def get_messages(self, conversation_id: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Get all messages for a specific conversation.

        Args:
            conversation_id (str, optional): Unique identifier for the conversation. Defaults to "default"
            user_id (str, optional): User identifier. Defaults to "anonymous"

        Returns:
            List[Dict[str, str]]: List of messages as dictionaries
        """
        user_id = self._get_user_id(user_id)
        conversation = self._get_or_create_conversation(self._get_conversation_id(conversation_id), user_id)
        return [msg.dict() for msg in conversation.messages]

    def add_message(self, message: Dict[str, str], conversation_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Add a new message to a conversation.

        Args:
            message (Dict[str, str]): Message to add
            conversation_id (str, optional): Conversation to add message to. Defaults to "default"
            user_id (str, optional): User identifier. Defaults to "anonymous"
        """
        user_id = self._get_user_id(user_id)
        conversation_id = self._get_conversation_id(conversation_id)
        conversation = self._get_or_create_conversation(conversation_id, user_id)
        chat_message = ChatMessage(**message)
        chat_message.conversation_id = conversation_id
        chat_message.user_id = user_id
        if "timestamp" not in message:
            chat_message.timestamp = datetime.utcnow()
        conversation.messages.append(chat_message)
        logger.info(f"Added message to conversation {conversation_id} for user {user_id}: {chat_message.content}")

    def add_response(self, response: Dict[str, str], agent_name: str, conversation_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Add an agent's response to a conversation.

        Args:
            response (Dict[str, str]): Response content
            agent_name (str): Name of the responding agent
            conversation_id (str, optional): Conversation to add response to. Defaults to "default"
            user_id (str, optional): User identifier. Defaults to "anonymous"
        """
        agent_response = AgentResponse(**response)
        # You may need to implement to_chat_message if not present
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
            error_message=agent_response.error_message
        )
        self.add_message(chat_message.dict(), self._get_conversation_id(conversation_id), self._get_user_id(user_id))
        logger.info(f"Added response from agent {agent_name} to conversation {conversation_id} for user {user_id}")

    def clear_messages(self, conversation_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Clear all messages in a conversation except the default message.

        Args:
            conversation_id (str, optional): Conversation to clear. Defaults to "default"
            user_id (str, optional): User identifier. Defaults to "anonymous"
        """
        user_id = self._get_user_id(user_id)
        conversation = self._get_or_create_conversation(self._get_conversation_id(conversation_id), user_id)
        conversation.messages = [self.default_message]  # Keep the initial message
        logger.info(f"Cleared message history for conversation {conversation_id} for user {user_id}")

    def get_last_message(self, conversation_id: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, str]:
        """
        Get the most recent message from a conversation.

        Args:
            conversation_id (str, optional): Conversation to get message from. Defaults to "default"
            user_id (str, optional): User identifier. Defaults to "anonymous"

        Returns:
            Dict[str, str]: Last message or empty dict if no messages
        """
        user_id = self._get_user_id(user_id)
        conversation = self._get_or_create_conversation(self._get_conversation_id(conversation_id), user_id)
        return conversation.messages[-1].dict() if conversation.messages else {}

    def get_chat_history(self, conversation_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
        """
        Get formatted chat history for a conversation.

        Args:
            conversation_id (str, optional): Conversation to get history for. Defaults to "default"
            user_id (str, optional): User identifier. Defaults to "anonymous"

        Returns:
            str: Formatted chat history as string
        """
        user_id = self._get_user_id(user_id)
        conversation = self._get_or_create_conversation(self._get_conversation_id(conversation_id), user_id)
        return "\n".join([f"{msg.role}: {msg.content}" for msg in conversation.messages])

    def get_all_conversation_ids(self, user_id: Optional[str] = None) -> List[str]:
        """
        Get a list of all conversation IDs for a specific user.

        Args:
            user_id (str, optional): User identifier. Defaults to "anonymous"

        Returns:
            List[str]: List of conversation IDs for the user
        """
        user_id = self._get_user_id(user_id)
        self._initialize_user(user_id)
        return list(self.user_conversations[user_id].keys())

    def get_all_user_ids(self) -> List[str]:
        """
        Get a list of all user IDs.

        Returns:
            List[str]: List of user IDs
        """
        return list(self.user_conversations.keys())

    def delete_conversation(self, conversation_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Delete a conversation by ID.

        Args:
            conversation_id (str, optional): ID of conversation to delete. Defaults to "default"
            user_id (str, optional): User identifier. Defaults to "anonymous"
        """
        user_id = self._get_user_id(user_id)
        conversation_id = self._get_conversation_id(conversation_id)
        self._initialize_user(user_id)
        if conversation_id in self.user_conversations[user_id]:
            del self.user_conversations[user_id][conversation_id]
            logger.info(f"Deleted conversation {conversation_id} for user {user_id}")

    def create_conversation(self, user_id: Optional[str] = None) -> str:
        """
        Create a new conversation for a user.

        Args:
            user_id (str, optional): User identifier. Defaults to "anonymous"

        Returns:
            str: ID of the created conversation
        """
        user_id = self._get_user_id(user_id)
        self._initialize_user(user_id)
        conversation_id = f"conversation_{len(self.user_conversations[user_id])}"
        while conversation_id in self.user_conversations[user_id]:
            conversation_id = f"conversation_{len(self.user_conversations[user_id])}_{int(time.time())}"
        self.user_conversations[user_id][conversation_id] = ConversationState(
            conversation_id=conversation_id,
            user_id=user_id,
            messages=[self.default_message],
            context={},
            memory={},
            agent_history=[],
            current_agent=None,
            last_message_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        logger.info(f"Created new conversation {conversation_id} for user {user_id}")
        return conversation_id

    def _get_or_create_conversation(self, conversation_id: str, user_id: str) -> ConversationState:
        """
        Get existing conversation or create new one if not exists.

        Args:
            conversation_id (str): Conversation ID to get/create
            user_id (str): User identifier

        Returns:
            ConversationState: Retrieved or created conversation
        """
        self._initialize_user(user_id)
        if conversation_id not in self.user_conversations[user_id]:
            self.user_conversations[user_id][conversation_id] = ConversationState(
                conversation_id=conversation_id,
                user_id=user_id,
                messages=[self.default_message],
                context={},
                memory={},
                agent_history=[],
                current_agent=None,
                last_message_id=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=True
            )
            logger.info(f"Created new conversation {conversation_id} for user {user_id}")
        return self.user_conversations[user_id][conversation_id]


# Create an instance to act as a singleton store
chat_manager_instance = ChatManager()
