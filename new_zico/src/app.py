import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agents.supervisor.simple_supervisor import SimpleSupervisor
from src.agents.config import Config
from src.models.chatMessage import (
    ChatMessage, 
    ConversationState, 
    AgentResponse, 
    MessageRole, 
    MessageStatus,
    AgentType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Zico Multi-Agent System",
    description="A sophisticated multi-agent system using LangGraph for intelligent conversation routing",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize supervisor
supervisor = SimpleSupervisor(Config.get_llm())

# In-memory storage for conversations (use database in production)
conversations: Dict[str, ConversationState] = {}


# Request/Response Models
class ChatRequest(BaseModel):
    """Request model for chat interactions"""
    message: str = Field(..., description="User message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    user_id: Optional[str] = Field("anonymous", description="User ID")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class ChatResponse(BaseModel):
    """Response model for chat interactions"""
    response: str = Field(..., description="Agent response")
    agent_name: str = Field(..., description="Name of the responding agent")
    agent_type: AgentType = Field(..., description="Type of the responding agent")
    conversation_id: str = Field(..., description="Conversation ID")
    message_id: str = Field(..., description="Message ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    next_agent: Optional[str] = Field(None, description="Next agent for followup")
    requires_followup: bool = Field(default=False, description="Whether followup is needed")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationListResponse(BaseModel):
    """Response model for conversation listing"""
    conversations: List[Dict[str, Any]] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total number of conversations")


# Utility functions
def get_conversation(conversation_id: str, user_id: str) -> ConversationState:
    """Get or create a conversation"""
    key = f"{user_id}:{conversation_id}"
    if key not in conversations:
        conversations[key] = ConversationState(
            conversation_id=conversation_id,
            user_id=user_id,
            messages=[],
            context={},
            memory={},
            agent_history=[]
        )
    return conversations[key]


def save_conversation(conversation: ConversationState):
    """Save conversation state"""
    key = f"{conversation.user_id}:{conversation.conversation_id}"
    conversations[key] = conversation


def create_chat_message(
    role: MessageRole,
    content: str,
    agent_name: Optional[str] = None,
    agent_type: Optional[AgentType] = None,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> ChatMessage:
    """Create a new chat message"""
    return ChatMessage(
        role=role,
        content=content,
        agent_name=agent_name,
        agent_type=agent_type,
        message_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        user_id=user_id,
        metadata=metadata or {},
        timestamp=datetime.utcnow()
    )


# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Zico Multi-Agent System is running",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """Main chat endpoint for multi-agent conversations"""
    try:
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())
        user_id = request.user_id or "anonymous"
        
        # Get or create conversation
        conversation = get_conversation(conversation_id, user_id)
        
        # Create user message
        user_message = create_chat_message(
            role=MessageRole.USER,
            content=request.message,
            conversation_id=conversation_id,
            user_id=user_id,
            metadata=request.context
        )
        
        # Add user message to conversation
        conversation.messages.append(user_message)
        conversation.last_message_id = user_message.message_id
        conversation.updated_at = datetime.utcnow()
        
        # Prepare messages for supervisor
        messages_for_supervisor = []
        for msg in conversation.messages[-10:]:  # Last 10 messages for context
            messages_for_supervisor.append({
                "role": msg.role.value,
                "content": msg.content
            })
        
        # Get response from supervisor
        logger.info(f"Invoking supervisor with {len(messages_for_supervisor)} messages")
        supervisor_response = supervisor.invoke(messages_for_supervisor, user_id, conversation_id)
        
        # Create agent response message
        agent_message = create_chat_message(
            role=MessageRole.AGENT,
            content=supervisor_response["response"],
            agent_name=supervisor_response["agent"],
            agent_type=AgentType.SUPERVISOR if supervisor_response["agent"] == "supervisor" else AgentType.CRYPTO_DATA,
            conversation_id=conversation_id,
            user_id=user_id,
            metadata={
                "agent_response": supervisor_response,
                "tools_used": supervisor_response.get("tools_used", []),
                "next_agent": supervisor_response.get("next_agent")
            }
        )
        
        # Add agent message to conversation
        conversation.messages.append(agent_message)
        conversation.current_agent = supervisor_response["agent"]
        conversation.updated_at = datetime.utcnow()
        
        # Update agent history
        conversation.agent_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "agent": supervisor_response["agent"],
            "message_id": agent_message.message_id,
            "success": True
        })
        
        # Save conversation
        save_conversation(conversation)
        
        # Background task to update conversation context
        background_tasks.add_task(update_conversation_context, conversation)
        
        return ChatResponse(
            response=supervisor_response["response"],
            agent_name=supervisor_response["agent"],
            agent_type=AgentType.SUPERVISOR if supervisor_response["agent"] == "supervisor" else AgentType.CRYPTO_DATA,
            conversation_id=conversation_id,
            message_id=agent_message.message_id,
            metadata=supervisor_response.get("metadata", {}),
            next_agent=supervisor_response.get("next_agent"),
            requires_followup=supervisor_response.get("requires_followup", False),
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/conversations/{user_id}", response_model=ConversationListResponse)
async def get_conversations(user_id: str = "anonymous"):
    """Get all conversations for a user"""
    try:
        user_conversations = []
        for key, conversation in conversations.items():
            if key.startswith(f"{user_id}:"):
                user_conversations.append({
                    "conversation_id": conversation.conversation_id,
                    "created_at": conversation.created_at,
                    "updated_at": conversation.updated_at,
                    "message_count": len(conversation.messages),
                    "current_agent": conversation.current_agent,
                    "is_active": conversation.is_active
                })
        
        return ConversationListResponse(
            conversations=user_conversations,
            total=len(user_conversations)
        )
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/conversations/{user_id}/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str, user_id: str = "anonymous"):
    """Get all messages for a specific conversation"""
    try:
        conversation = get_conversation(conversation_id, user_id)
        return {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "messages": [msg.dict() for msg in conversation.messages],
            "total_messages": len(conversation.messages)
        }
    except Exception as e:
        logger.error(f"Error getting conversation messages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.delete("/conversations/{user_id}/{conversation_id}")
async def delete_conversation(conversation_id: str, user_id: str = "anonymous"):
    """Delete a conversation"""
    try:
        key = f"{user_id}:{conversation_id}"
        if key in conversations:
            del conversations[key]
            return {"message": f"Conversation {conversation_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Conversation not found")
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/conversations/{user_id}/reset")
async def reset_conversation(conversation_id: str, user_id: str = "anonymous"):
    """Reset a conversation (clear messages but keep conversation)"""
    try:
        conversation = get_conversation(conversation_id, user_id)
        conversation.messages = []
        conversation.context = {}
        conversation.agent_history = []
        conversation.current_agent = None
        conversation.updated_at = datetime.utcnow()
        save_conversation(conversation)
        
        return {"message": f"Conversation {conversation_id} reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting conversation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Background tasks
async def update_conversation_context(conversation: ConversationState):
    """Update conversation context based on recent messages"""
    try:
        # Extract key information from recent messages
        recent_messages = conversation.messages[-5:]  # Last 5 messages
        
        # Update context based on message content
        context_updates = {}
        for msg in recent_messages:
            if msg.role == MessageRole.USER:
                # Extract entities, topics, etc.
                content_lower = msg.content.lower()
                if any(word in content_lower for word in ["bitcoin", "eth", "crypto", "price"]):
                    context_updates["crypto_related"] = True
                if any(word in content_lower for word in ["nft", "floor price"]):
                    context_updates["nft_related"] = True
        
        # Update conversation context
        conversation.context.update(context_updates)
        conversation.updated_at = datetime.utcnow()
        save_conversation(conversation)
        
    except Exception as e:
        logger.error(f"Error updating conversation context: {str(e)}", exc_info=True)


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return {"error": "Internal server error", "detail": str(exc)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

