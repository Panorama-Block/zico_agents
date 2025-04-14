import logging
from fastapi import APIRouter, Query, Body
from src.stores import chat_manager_instance
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/messages")
async def get_messages(conversation_id: str = Query(default="default"), user_id: str = Query(default="anonymous")):
    """Get all chat messages for a conversation"""
    logger.info(f"Received get_messages request for conversation {conversation_id} from user {user_id}")
    return {"messages": chat_manager_instance.get_messages(conversation_id, user_id)}


@router.get("/clear")
async def clear_messages(conversation_id: str = Query(default="default"), user_id: str = Query(default="anonymous")):
    """Clear chat message history for a conversation"""
    logger.info(f"Clearing message history for conversation {conversation_id} for user {user_id}")
    chat_manager_instance.clear_messages(conversation_id, user_id)
    return {"response": "successfully cleared message history"}


@router.get("/conversations")
async def get_conversations(user_id: str = Query(default="anonymous")):
    """Get all conversation IDs for a specific user"""
    logger.info(f"Getting all conversation IDs for user {user_id}")
    return {"conversation_ids": chat_manager_instance.get_all_conversation_ids(user_id)}


@router.get("/users")
async def get_users():
    """Get all user IDs"""
    logger.info("Getting all user IDs")
    return {"user_ids": chat_manager_instance.get_all_user_ids()}


class UserIdRequest(BaseModel):
    user_id: str


@router.post("/conversations")
async def create_conversation(
    user_id_query: str = Query(default=None, alias="user_id"),
    user_id_body: Optional[UserIdRequest] = None,
    user_id_str: Optional[str] = Body(default=None)
):
    """Create a new conversation for a specific user"""
    user_id = None
    if user_id_body:
        user_id = user_id_body.user_id
    elif user_id_str:
        user_id = user_id_str
    else:
        user_id = user_id_query

    if not user_id:
        user_id = "anonymous"
        
    logger.info(f"Creating new conversation for user {user_id}")
    conversation_id = chat_manager_instance.create_conversation(user_id)
    return {"conversation_id": conversation_id}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user_id: str = Query(default="anonymous")):
    """Delete a conversation for a specific user"""
    logger.info(f"Deleting conversation {conversation_id} for user {user_id}")
    chat_manager_instance.delete_conversation(conversation_id, user_id)
    return {"response": f"successfully deleted conversation {conversation_id}"}
