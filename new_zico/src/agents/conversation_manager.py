import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json

from src.models.chatMessage import ConversationState, ChatMessage, MessageRole, AgentType

logger = logging.getLogger(__name__)


@dataclass
class ConversationMetadata:
    """Metadata for conversation tracking"""
    conversation_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    current_agent: Optional[str]
    is_active: bool
    context_summary: Dict[str, Any]


class ConversationManager:
    """Manages conversation state and persistence for multi-agent system"""
    
    def __init__(self):
        self.conversations: Dict[str, ConversationState] = {}
        self.metadata: Dict[str, ConversationMetadata] = {}
        self.user_conversations: Dict[str, List[str]] = {}
        
    def create_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> str:
        """Create a new conversation"""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        key = f"{user_id}:{conversation_id}"
        
        # Create conversation state
        conversation_state = ConversationState(
            conversation_id=conversation_id,
            user_id=user_id,
            messages=[],
            context={},
            memory={},
            agent_history=[],
            current_agent=None,
            last_message_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        # Create metadata
        metadata = ConversationMetadata(
            conversation_id=conversation_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_count=0,
            current_agent=None,
            is_active=True,
            context_summary={}
        )
        
        # Store conversation
        self.conversations[key] = conversation_state
        self.metadata[key] = metadata
        
        # Update user conversations
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        self.user_conversations[user_id].append(conversation_id)
        
        logger.info(f"Created conversation {conversation_id} for user {user_id}")
        return conversation_id
    
    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[ConversationState]:
        """Get conversation by ID and user"""
        key = f"{user_id}:{conversation_id}"
        return self.conversations.get(key)
    
    def get_or_create_conversation(self, conversation_id: str, user_id: str) -> ConversationState:
        """Get existing conversation or create new one"""
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            self.create_conversation(user_id, conversation_id)
            conversation = self.get_conversation(conversation_id, user_id)
        return conversation
    
    def add_message(self, conversation_id: str, user_id: str, message: ChatMessage) -> None:
        """Add message to conversation"""
        conversation = self.get_or_create_conversation(conversation_id, user_id)
        key = f"{user_id}:{conversation_id}"
        
        # Add message
        conversation.messages.append(message)
        conversation.last_message_id = message.message_id
        conversation.updated_at = datetime.utcnow()
        
        # Update metadata
        if key in self.metadata:
            self.metadata[key].message_count = len(conversation.messages)
            self.metadata[key].updated_at = datetime.utcnow()
            self.metadata[key].current_agent = conversation.current_agent
        
        logger.info(f"Added message to conversation {conversation_id}")
    
    def update_conversation_context(self, conversation_id: str, user_id: str, context_updates: Dict[str, Any]) -> None:
        """Update conversation context"""
        conversation = self.get_conversation(conversation_id, user_id)
        if conversation:
            conversation.context.update(context_updates)
            conversation.updated_at = datetime.utcnow()
            
            # Update metadata
            key = f"{user_id}:{conversation_id}"
            if key in self.metadata:
                self.metadata[key].context_summary.update(context_updates)
                self.metadata[key].updated_at = datetime.utcnow()
    
    def update_agent_history(self, conversation_id: str, user_id: str, agent_info: Dict[str, Any]) -> None:
        """Update agent interaction history"""
        conversation = self.get_conversation(conversation_id, user_id)
        if conversation:
            conversation.agent_history.append(agent_info)
            conversation.updated_at = datetime.utcnow()
    
    def get_conversation_messages(self, conversation_id: str, user_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        """Get messages from conversation"""
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return []
        
        messages = conversation.messages
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    def get_user_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all conversations for a user"""
        user_conversations = []
        
        for conversation_id in self.user_conversations.get(user_id, []):
            key = f"{user_id}:{conversation_id}"
            metadata = self.metadata.get(key)
            
            if metadata:
                user_conversations.append(asdict(metadata))
        
        return user_conversations
    
    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete a conversation"""
        key = f"{user_id}:{conversation_id}"
        
        if key in self.conversations:
            del self.conversations[key]
            
        if key in self.metadata:
            del self.metadata[key]
        
        # Remove from user conversations
        if user_id in self.user_conversations:
            if conversation_id in self.user_conversations[user_id]:
                self.user_conversations[user_id].remove(conversation_id)
        
        logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
        return True
    
    def reset_conversation(self, conversation_id: str, user_id: str) -> None:
        """Reset conversation (clear messages but keep conversation)"""
        conversation = self.get_conversation(conversation_id, user_id)
        if conversation:
            conversation.messages = []
            conversation.context = {}
            conversation.agent_history = []
            conversation.current_agent = None
            conversation.last_message_id = None
            conversation.updated_at = datetime.utcnow()
            
            # Update metadata
            key = f"{user_id}:{conversation_id}"
            if key in self.metadata:
                self.metadata[key].message_count = 0
                self.metadata[key].current_agent = None
                self.metadata[key].context_summary = {}
                self.metadata[key].updated_at = datetime.utcnow()
    
    def cleanup_old_conversations(self, max_age_hours: int = 24) -> int:
        """Clean up old conversations"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        deleted_count = 0
        
        conversations_to_delete = []
        
        for key, metadata in self.metadata.items():
            if metadata.updated_at < cutoff_time and not metadata.is_active:
                conversations_to_delete.append(key)
        
        for key in conversations_to_delete:
            user_id, conversation_id = key.split(":", 1)
            if self.delete_conversation(conversation_id, user_id):
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old conversations")
        return deleted_count
    
    def get_conversation_stats(self, user_id: str) -> Dict[str, Any]:
        """Get conversation statistics for a user"""
        user_conversations = self.get_user_conversations(user_id)
        
        total_conversations = len(user_conversations)
        active_conversations = sum(1 for conv in user_conversations if conv["is_active"])
        total_messages = sum(conv["message_count"] for conv in user_conversations)
        
        # Agent usage statistics
        agent_usage = {}
        for conv in user_conversations:
            conversation = self.get_conversation(conv["conversation_id"], user_id)
            if conversation:
                for agent_info in conversation.agent_history:
                    agent_name = agent_info.get("agent", "unknown")
                    agent_usage[agent_name] = agent_usage.get(agent_name, 0) + 1
        
        return {
            "total_conversations": total_conversations,
            "active_conversations": active_conversations,
            "total_messages": total_messages,
            "agent_usage": agent_usage,
            "average_messages_per_conversation": total_messages / total_conversations if total_conversations > 0 else 0
        }
    
    def export_conversation(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """Export conversation data"""
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return {}
        
        return {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "messages": [msg.dict() for msg in conversation.messages],
            "context": conversation.context,
            "agent_history": conversation.agent_history,
            "metadata": asdict(self.metadata.get(f"{user_id}:{conversation_id}", {}))
        }
    
    def import_conversation(self, conversation_data: Dict[str, Any]) -> str:
        """Import conversation data"""
        conversation_id = conversation_data.get("conversation_id", str(uuid.uuid4()))
        user_id = conversation_data.get("user_id", "anonymous")
        
        # Create conversation
        self.create_conversation(user_id, conversation_id)
        
        # Import messages
        for msg_data in conversation_data.get("messages", []):
            message = ChatMessage(**msg_data)
            self.add_message(conversation_id, user_id, message)
        
        # Import context and history
        conversation = self.get_conversation(conversation_id, user_id)
        if conversation:
            conversation.context.update(conversation_data.get("context", {}))
            conversation.agent_history.extend(conversation_data.get("agent_history", []))
        
        return conversation_id


# Global conversation manager instance
conversation_manager = ConversationManager() 