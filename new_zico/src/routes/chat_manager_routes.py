import logging
from fastapi import APIRouter, Query, Body, HTTPException, Depends
from src.service.chat_manager import StoragePersistenceError, chat_manager_instance
from src.agents.config import Config
from typing import Optional
from pydantic import BaseModel
from typing import Dict

from src.security.chat_auth import PanoramaPrincipal, require_chat_principal

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
async def get_messages(
    conversation_id: str = Query(default="default"),
    user_id: str = Query(default="anonymous"),
    principal: PanoramaPrincipal = Depends(require_chat_principal),
):
    """Get all chat messages for a conversation"""
    logger.info(
        "Received get_messages request for conversation %s from authenticated user %s",
        conversation_id,
        principal.user_id,
    )
    return {
        "messages": chat_manager_instance.get_messages(
            conversation_id,
            principal.user_id,
        )
    }


@router.get("/conversations")
async def get_conversations(
    user_id_query: str = Query(default=None, alias="user_id"),
    user_id_str: Optional[str] = Body(default=None),
    principal: PanoramaPrincipal = Depends(require_chat_principal),
):
    """Get all conversations for the authenticated user"""
    logger.info(
        "Getting all conversations for authenticated user %s",
        principal.user_id,
    )
    conversations = chat_manager_instance.get_conversations(
        principal.user_id
    )
    return {"conversations": conversations}


@router.post("/conversations")
async def create_conversation(
    user_id_query: str = Query(default=None, alias="user_id"),
    body: Optional[Dict[str, str]] = Body(default=None),
    principal: PanoramaPrincipal = Depends(require_chat_principal),
):
    """Create a new conversation for the authenticated user"""
    logger.info(
        "Creating new conversation for authenticated user %s",
        principal.user_id,
    )
    try:
        conversation_id = chat_manager_instance.create_conversation(
            principal.user_id
        )
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
    user_id_body: Dict[str, str] = Body(default=None),
    principal: PanoramaPrincipal = Depends(require_chat_principal),
):
    """Delete a conversation owned by the authenticated user"""
    logger.info(
        "Deleting conversation %s for authenticated user %s",
        conversation_id,
        principal.user_id,
    )
    chat_manager_instance.delete_conversation(
        conversation_id,
        principal.user_id,
    )
    return {"response": "successfully deleted conversation"}


class GenerateTitleRequest(BaseModel):
    user_id: str
    conversation_id: str
    message: str


@router.post("/generate-title")
async def generate_title(
    body: GenerateTitleRequest,
    principal: PanoramaPrincipal = Depends(require_chat_principal),
):
    """Use a lightweight LLM call to generate a short title from the first user message."""
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    try:
        llm = Config.get_llm(model="gemini-2.0-flash", temperature=0.3, with_cost_tracking=False)
        prompt = _TITLE_PROMPT.format(message=body.message[:500])
        result = llm.invoke(prompt)
        title = (result.content if hasattr(result, "content") else str(result)).strip().strip('"\'')
        # Enforce 8-word max
        words = title.split()
        if len(words) > 8:
            title = " ".join(words[:8])
        if not title:
            title = body.message[:50]
    except Exception as exc:
        logger.warning("LLM title generation failed, falling back to truncation: %s", exc)
        title = (body.message[:47] + "...") if len(body.message) > 50 else body.message

    logger.info(
        "Persisting AI title for authenticated user=%s conversation=%s title=%r",
        principal.user_id,
        body.conversation_id,
        title,
    )
    chat_manager_instance.update_conversation_title(
        body.conversation_id,
        principal.user_id,
        title=title,
    )
    logger.info("AI title persisted successfully")

    return {"title": title}
