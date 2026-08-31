import logging
from fastapi import APIRouter, Query, Body, HTTPException
from src.service.chat_manager import (
    ConversationNotFoundError,
    StoragePersistenceError,
    chat_manager_instance,
)
from src.agents.config import Config
from typing import Optional
from pydantic import BaseModel
from typing import Dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

_TITLE_PROMPT = (
    "Summarize the following user message into a short chat title (3 to 8 words). "
    "Return ONLY the title text, nothing else. No quotes, no punctuation at the end.\n\n"
    "User message: {message}"
)

class UserIdRequest(BaseModel):
    user_id: str

@router.get("/messages")
async def get_messages(conversation_id: str = Query(default="default"), user_id: str = Query(default="anonymous")):
    """Get all chat messages for a conversation without mutating persistence."""
    logger.info(f"Received get_messages request for conversation {conversation_id} from user {user_id}")
    return {"messages": chat_manager_instance.get_messages(conversation_id, user_id)}


@router.get("/clear")
async def clear_messages(conversation_id: str = Query(default="default"), user_id: str = Query(default="anonymous")):
    """Clear chat message history for a conversation."""
    logger.info(f"Clearing message history for conversation {conversation_id} for user {user_id}")
    try:
        chat_manager_instance.clear_messages(conversation_id, user_id)
    except StoragePersistenceError as exc:
        raise HTTPException(
            status_code=503,
            detail="Chat persistence is currently unavailable. Conversation was not cleared.",
        ) from exc
    return {"response": "successfully cleared message history"}


@router.get("/conversations")
async def get_conversations(
    user_id_query: str = Query(default=None, alias="user_id"),
    user_id_str: Optional[str] = Body(default=None)
):
    """Get all conversations using domain conversation IDs, not gateway resource IDs."""
    user_id = user_id_str if user_id_str else user_id_query

    if not user_id:
        user_id = "anonymous"

    logger.info(f"Getting all conversations for user {user_id}")
    conversations = chat_manager_instance.get_conversations(user_id)
    return {"conversations": conversations}


@router.get("/users")
async def get_users():
    """Get all user IDs"""
    logger.info("Getting all user IDs")
    return {"user_ids": chat_manager_instance.get_all_user_ids()}


@router.post("/conversations")
async def create_conversation(
    user_id_query: str = Query(default=None, alias="user_id"),
    body: Optional[Dict[str, str]] = Body(default=None)
):
    """Create a new conversation for a specific user"""
    user_id = user_id_query
    if isinstance(body, dict):
        payload_user_id = body.get("user_id")
        if isinstance(payload_user_id, str) and payload_user_id.strip():
            user_id = payload_user_id.strip()

    if not user_id:
        user_id = "anonymous"

    logger.info(f"Creating new conversation for user {user_id}")
    try:
        conversation_id = chat_manager_instance.create_conversation(user_id)
    except StoragePersistenceError as exc:
        raise HTTPException(
            status_code=503,
            detail="Chat persistence is currently unavailable. Conversation was not created.",
        ) from exc
    return {"conversation_id": conversation_id}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id_query: str = Query(default=None, alias="user_id"),
    user_id_body: Dict[str, str] = Body(default=None)
):
    """Delete a persisted conversation by its domain conversation ID."""
    user_id = user_id_body.get("user_id") if user_id_body else user_id_query

    if not user_id:
        user_id = "anonymous"

    logger.info(f"Deleting conversation {conversation_id} for user {user_id}")
    try:
        chat_manager_instance.delete_conversation(conversation_id, user_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc
    except StoragePersistenceError as exc:
        raise HTTPException(
            status_code=503,
            detail="Chat persistence is currently unavailable. Conversation was not deleted.",
        ) from exc
    return {"response": "successfully deleted conversation", "conversation_id": conversation_id}


class GenerateTitleRequest(BaseModel):
    user_id: str
    conversation_id: str
    message: str


@router.post("/generate-title")
async def generate_title(body: GenerateTitleRequest):
    """Use a lightweight LLM call to generate a short title from the first user message."""
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    try:
        llm = Config.get_llm(model="gemini-2.0-flash", temperature=0.3, with_cost_tracking=False)
        prompt = _TITLE_PROMPT.format(message=body.message[:500])
        result = llm.invoke(prompt)
        title = (result.content if hasattr(result, "content") else str(result)).strip().strip('"\'')
        words = title.split()
        if len(words) > 8:
            title = " ".join(words[:8])
        if not title:
            title = body.message[:50]
    except Exception as exc:
        logger.warning("LLM title generation failed, falling back to truncation: %s", exc)
        title = (body.message[:47] + "...") if len(body.message) > 50 else body.message

    try:
        logger.info(
            "Persisting AI title for user=%s conversation=%s title=%r",
            body.user_id, body.conversation_id, title,
        )
        chat_manager_instance.update_conversation_title(
            body.conversation_id,
            body.user_id,
            title=title,
        )
        logger.info("AI title persisted successfully")
    except Exception as exc:
        logger.warning("Failed to persist generated title: %s", exc, exc_info=True)

    return {"title": title}
