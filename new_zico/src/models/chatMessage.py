from typing import TypedDict, Literal, List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Enum for message roles"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    AGENT = "agent"


class AgentType(str, Enum):
    """Enum for different agent types"""
    SUPERVISOR = "supervisor"
    CRYPTO_DATA = "crypto_data"
    GENERAL = "general"
    RESEARCH = "research"
    ANALYSIS = "analysis"


class MessageStatus(str, Enum):
    """Enum for message processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChatMessage(BaseModel):
    """Enhanced chat message model for multi-agent conversations"""
    
    # Core message fields
    role: MessageRole = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Message content")
    
    # Agent-specific fields
    agent_name: Optional[str] = Field(None, description="Name of the agent that processed this message")
    agent_type: Optional[AgentType] = Field(None, description="Type of agent that processed this message")
    
    # Metadata and context
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    message_id: Optional[str] = Field(None, description="Unique message identifier")
    
    # Processing status
    status: MessageStatus = Field(default=MessageStatus.COMPLETED, description="Message processing status")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    
    # Conversation context
    conversation_id: Optional[str] = Field(None, description="Conversation identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    
    # Tool calls and responses
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls made by the agent")
    tool_results: Optional[List[Dict[str, Any]]] = Field(None, description="Results from tool executions")
    
    # Multi-turn conversation support
    next_agent: Optional[str] = Field(None, description="Next agent to handle the conversation")
    requires_followup: bool = Field(default=False, description="Whether this message requires followup")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConversationState(BaseModel):
    """State management for multi-agent conversations"""
    
    conversation_id: str = Field(..., description="Unique conversation identifier")
    user_id: str = Field(..., description="User identifier")
    
    # Current state
    current_agent: Optional[str] = Field(None, description="Currently active agent")
    last_message_id: Optional[str] = Field(None, description="ID of the last message")
    
    # Conversation history
    messages: List[ChatMessage] = Field(default_factory=list, description="Message history")
    
    # Context and memory
    context: Dict[str, Any] = Field(default_factory=dict, description="Conversation context")
    memory: Dict[str, Any] = Field(default_factory=dict, description="Persistent memory across turns")
    
    # Agent routing history
    agent_history: List[Dict[str, Any]] = Field(default_factory=list, description="History of agent interactions")
    
    # Status and metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True, description="Whether conversation is active")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentResponse(BaseModel):
    """Standardized response format for agents"""
    
    content: str = Field(..., description="Response content")
    agent_name: str = Field(..., description="Name of the responding agent")
    agent_type: AgentType = Field(..., description="Type of the responding agent")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Tool information
    tools_used: List[str] = Field(default_factory=list, description="Tools used in this response")
    tool_results: Optional[List[Dict[str, Any]]] = Field(None, description="Results from tool executions")
    
    # Next steps
    next_agent: Optional[str] = Field(None, description="Next agent to handle the conversation")
    requires_followup: bool = Field(default=False, description="Whether followup is needed")
    
    # Status
    success: bool = Field(default=True, description="Whether the response was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# TypedDict for backward compatibility
class ChatMessageDict(TypedDict):
    role: str
    content: str
    agent_name: Optional[str]
    metadata: Dict[str, Any]
    timestamp: str
    message_id: Optional[str]
    status: str
    conversation_id: Optional[str]
    user_id: Optional[str]

