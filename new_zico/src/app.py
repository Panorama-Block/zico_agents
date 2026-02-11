import asyncio
import base64
import json
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from src.infrastructure.logging import setup_logging, get_logger
from src.infrastructure.rate_limiter import setup_rate_limiter, limiter
from src.agents.config import Config
from src.graphs.factory import build_graph
from src.graphs.nodes import initialize_agents
from src.models.chatMessage import ChatMessage
from src.routes.chat_manager_routes import router as chat_manager_router
from src.service.chat_manager import chat_manager_instance
from src.agents.crypto_data.tools import get_coingecko_id, get_tradingview_symbol
from src.agents.metadata import metadata

# Setup structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_format = os.getenv("LOG_FORMAT", "color")
setup_logging(level=log_level, format_type=log_format)
logger = get_logger(__name__)

logger.info("Starting Zico Agent API (StateGraph architecture)")

# Initialize FastAPI app
app = FastAPI(
    title="Zico Agent API",
    version="3.0",
    description="Multi-agent AI assistant with deterministic StateGraph routing",
)

# Setup rate limiting
setup_rate_limiter(app)

# Enable CORS for local/frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agents and compile the StateGraph
initialize_agents()
graph = build_graph()


class ChatRequest(BaseModel):
    message: ChatMessage
    chain_id: str = "default"
    wallet_address: str = "default"
    conversation_id: str = "default"
    user_id: str = "anonymous"
    metadata: Dict[str, Any] | None = None


# Lightweight in-memory agent config for frontend integrations
AVAILABLE_AGENTS = [
    {"name": "default", "human_readable_name": "Default General Purpose", "description": "General chat and meta-queries about agents."},
    {"name": "crypto data", "human_readable_name": "Crypto Data Fetcher", "description": "Real-time cryptocurrency prices, market cap, FDV, TVL."},
    {"name": "token swap", "human_readable_name": "Token Swap Agent", "description": "Swap tokens using supported DEX APIs."},
    {"name": "realtime search", "human_readable_name": "Real-Time Search", "description": "Search the web for recent information."},
    {"name": "dexscreener", "human_readable_name": "DexScreener Analyst", "description": "Fetches and analyzes DEX trading data."},
    {"name": "rugcheck", "human_readable_name": "Token Safety Analyzer", "description": "Analyzes token safety and trends (Solana)."},
    {"name": "imagen", "human_readable_name": "Image Generator", "description": "Generate images from text prompts."},
    {"name": "rag", "human_readable_name": "Document Assistant", "description": "Answer questions about uploaded documents."},
    {"name": "tweet sizzler", "human_readable_name": "Tweet / X-Post Generator", "description": "Generate engaging tweets."},
    {"name": "dca", "human_readable_name": "DCA Strategy Manager", "description": "Plan and manage DCA strategies."},
    {"name": "base", "human_readable_name": "Base Transaction Manager", "description": "Handle transactions on Base network."},
    {"name": "mor rewards", "human_readable_name": "MOR Rewards Tracker", "description": "Track MOR rewards and balances."},
    {"name": "mor claims", "human_readable_name": "MOR Claims Agent", "description": "Claim MOR tokens."},
    {"name": "lending", "human_readable_name": "Lending Agent", "description": "Supply, borrow, repay, or withdraw assets."},
]

# Default to a small, reasonable subset
SELECTED_AGENTS = [agent["name"] for agent in AVAILABLE_AGENTS[:6]]

# Commands exposed to the ChatInput autocomplete
AGENT_COMMANDS = [
    {"command": "morpheus", "name": "Default General Purpose", "description": "General assistant for simple queries and meta-questions."},
    {"command": "crypto", "name": "Crypto Data Fetcher", "description": "Get prices, market cap, FDV, TVL and more."},
    {"command": "document", "name": "Document Assistant", "description": "Ask questions about uploaded documents."},
    {"command": "tweet", "name": "Tweet / X-Post Generator", "description": "Create engaging tweets about crypto and web3."},
    {"command": "search", "name": "Real-Time Search", "description": "Search the web for recent events or updates."},
    {"command": "dexscreener", "name": "DexScreener Analyst", "description": "Analyze DEX trading data on supported chains."},
    {"command": "rugcheck", "name": "Token Safety Analyzer", "description": "Check token safety and view trending tokens."},
    {"command": "dca", "name": "DCA Strategy Manager", "description": "Plan a dollar-cost averaging strategy."},
    {"command": "base", "name": "Base Transaction Manager", "description": "Send tokens and swap on Base."},
    {"command": "rewards", "name": "MOR Rewards Tracker", "description": "Check rewards balance and accrual."},
    {"command": "lending", "name": "Lending Agent", "description": "Supply, borrow, repay, or withdraw assets."},
]


# Agents endpoints expected by the frontend
@app.get("/agents/available")
def get_available_agents():
    return {
        "selected_agents": SELECTED_AGENTS,
        "available_agents": AVAILABLE_AGENTS,
    }


@app.post("/agents/selected")
async def set_selected_agents(request: Request):
    global SELECTED_AGENTS
    data = await request.json()
    agents = data.get("agents", [])
    available_names = {a["name"] for a in AVAILABLE_AGENTS}
    valid_agents = [a for a in agents if a in available_names]
    if not valid_agents:
        return {"status": "no_change", "agents": SELECTED_AGENTS}
    SELECTED_AGENTS = valid_agents[:6]
    return {"status": "success", "agents": SELECTED_AGENTS}


@app.get("/agents/commands")
def get_agent_commands():
    return {"commands": AGENT_COMMANDS}


# Map agent runtime names to high-level types for storage/analytics
def _map_agent_type(agent_name: str) -> str:
    mapping = {
        "crypto_agent": "crypto data",
        "default_agent": "default",
        "database_agent": "analysis",
        "search_agent": "realtime search",
        "swap_agent": "token swap",
        "lending_agent": "lending",
        "staking_agent": "staking",
        "supervisor": "supervisor",
    }
    return mapping.get(agent_name, "supervisor")


def _sanitize_user_message_content(content: str | None) -> str | None:
    """Strip wrapper prompts (e.g., 'User Message: ...') the frontend might send."""
    if not content:
        return content
    text = content.strip()
    marker = "user message:"
    lowered = text.lower()
    idx = lowered.rfind(marker)
    if idx != -1:
        candidate = text[idx + len(marker) :].strip()
        if candidate:
            return candidate
    return text


def _resolve_identity(request: ChatRequest) -> tuple[str, str]:
    """Ensure each request has a stable user and conversation identifier."""
    user_id = (request.user_id or "").strip()
    if not user_id or user_id.lower() == "anonymous":
        wallet = (request.wallet_address or "").strip()
        if wallet and wallet.lower() != "default":
            user_id = f"wallet::{wallet.lower()}"
        else:
            raise HTTPException(
                status_code=400,
                detail="A stable 'user_id' or wallet_address is required for swap operations.",
            )

    conversation_id = (request.conversation_id or "").strip() or "default"
    return user_id, conversation_id


def _invoke_graph(
    conversation_messages,
    user_id,
    conversation_id,
    *,
    pre_classified: Dict[str, Any] | None = None,
):
    """Invoke the StateGraph and return the result state.

    If *pre_classified* is provided (e.g. from audio transcription) its
    fields are merged into the initial state so the semantic router can
    skip the embedding call.
    """
    initial_state: Dict[str, Any] = {
        "messages": conversation_messages,
        "user_id": user_id,
        "conversation_id": conversation_id,
    }
    if pre_classified:
        initial_state.update(pre_classified)
    return graph.invoke(initial_state)


def _build_response_payload(result, user_id, conversation_id, extra_fields=None):
    """Build the HTTP response from graph result state."""
    final_response = result.get("final_response", "No response available")
    response_agent = result.get("response_agent", "supervisor")
    response_metadata = result.get("response_metadata", {})
    nodes_executed = result.get("nodes_executed", [])

    agent_name = _map_agent_type(response_agent)

    # Build response metadata and enrich
    full_metadata = {"supervisor_result": result}
    swap_meta_snapshot = None

    if response_metadata:
        full_metadata.update(response_metadata)
    elif agent_name == "token swap":
        swap_meta = metadata.get_swap_agent(user_id=user_id, conversation_id=conversation_id)
        if swap_meta:
            full_metadata.update(swap_meta)
            swap_meta_snapshot = swap_meta
    elif agent_name == "lending":
        lending_meta = metadata.get_lending_agent(user_id=user_id, conversation_id=conversation_id)
        if lending_meta:
            full_metadata.update(lending_meta)
    elif agent_name == "staking":
        staking_meta = metadata.get_staking_agent(user_id=user_id, conversation_id=conversation_id)
        if staking_meta:
            full_metadata.update(staking_meta)

    # Create and store the response message
    response_message = ChatMessage(
        role="assistant",
        content=final_response,
        agent_name=agent_name,
        agent_type=_map_agent_type(agent_name),
        metadata=response_metadata,
        conversation_id=conversation_id,
        user_id=user_id,
        requires_action=True if agent_name in ["token swap", "lending", "staking"] else False,
        action_type="swap" if agent_name == "token swap" else "lending" if agent_name == "lending" else "staking" if agent_name == "staking" else None,
    )

    chat_manager_instance.add_message(
        message=response_message.dict(),
        conversation_id=conversation_id,
        user_id=user_id,
    )

    # Build payload
    response_payload = {
        "response": final_response,
        "agentName": agent_name,
        "nodesExecuted": nodes_executed,
    }

    # Add extra fields (e.g. transcription for audio)
    if extra_fields:
        response_payload.update(extra_fields)

    # Resolve metadata for payload
    response_meta = response_metadata or {}
    if agent_name == "token swap" and not response_meta:
        if swap_meta_snapshot:
            response_meta = swap_meta_snapshot
        else:
            swap_meta = metadata.get_swap_agent(user_id=user_id, conversation_id=conversation_id)
            if swap_meta:
                response_meta = swap_meta

    if response_meta:
        response_payload["metadata"] = response_meta

    # Clear metadata after ready events
    _clear_ready_metadata(agent_name, response_meta, user_id, conversation_id)

    return response_payload


def _clear_ready_metadata(agent_name, response_meta, user_id, conversation_id):
    """Clear DeFi metadata when intent is ready for execution."""
    if not response_meta or not isinstance(response_meta, dict):
        return

    status = response_meta.get("status")
    event = response_meta.get("event")

    if agent_name == "token swap" and (status == "ready" or event == "swap_intent_ready"):
        metadata.set_swap_agent({}, user_id=user_id, conversation_id=conversation_id)
    elif agent_name == "lending" and (status == "ready" or event == "lending_intent_ready"):
        metadata.set_lending_agent({}, user_id=user_id, conversation_id=conversation_id)
    elif agent_name == "staking" and (status == "ready" or event == "staking_intent_ready"):
        metadata.set_staking_agent({}, user_id=user_id, conversation_id=conversation_id)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/costs")
def get_costs():
    """Get current LLM cost summary."""
    cost_tracker = Config.get_cost_tracker()
    return cost_tracker.get_summary()


@app.get("/costs/detailed")
def get_detailed_costs():
    """Get detailed LLM cost report."""
    cost_tracker = Config.get_cost_tracker()
    return cost_tracker.get_detailed_report()


@app.get("/costs/conversation")
def get_conversation_costs(request: Request):
    """Get accumulated LLM costs for a specific conversation."""
    params = request.query_params
    conversation_id = params.get("conversation_id")
    user_id = params.get("user_id")

    if not conversation_id or not user_id:
        raise HTTPException(
            status_code=400,
            detail="Both 'conversation_id' and 'user_id' query parameters are required.",
        )

    costs = chat_manager_instance.get_conversation_costs(
        conversation_id=conversation_id,
        user_id=user_id,
    )
    return {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "costs": costs,
    }


@app.get("/models")
def get_available_models():
    """List available LLM models."""
    return {
        "models": Config.list_available_models(),
        "providers": Config.list_available_providers(),
        "default": Config.DEFAULT_MODEL,
    }


@app.get("/chat/messages")
def get_messages(request: Request):
    params = request.query_params
    conversation_id = params.get("conversation_id", "default")
    user_id = params.get("user_id", "anonymous")
    return {"messages": chat_manager_instance.get_messages(conversation_id, user_id)}


@app.get("/chat/conversations")
def get_conversations(request: Request):
    params = request.query_params
    user_id = params.get("user_id", "anonymous")
    return {"conversation_ids": chat_manager_instance.get_all_conversation_ids(user_id)}


@app.post("/chat")
def chat(request: ChatRequest):
    user_id: str | None = None
    conversation_id: str | None = None
    try:
        logger.debug("Received chat payload: %s", request.model_dump())
        user_id, conversation_id = _resolve_identity(request)
        logger.debug(
            "Resolved chat identity user=%s conversation=%s wallet=%s",
            user_id,
            conversation_id,
            (request.wallet_address or "").strip() if request.wallet_address else None,
        )

        wallet = request.wallet_address.strip() if request.wallet_address else None
        if wallet and wallet.lower() == "default":
            wallet = None
        display_name = None
        if isinstance(request.message.metadata, dict):
            display_name = request.message.metadata.get("display_name")

        chat_manager_instance.ensure_session(
            user_id,
            conversation_id,
            wallet_address=wallet,
            display_name=display_name,
        )

        if request.message.role == "user":
            clean_content = _sanitize_user_message_content(request.message.content)
            if clean_content is not None:
                request.message.content = clean_content

        # Add the user message to the conversation
        chat_manager_instance.add_message(
            message=request.message.dict(),
            conversation_id=conversation_id,
            user_id=user_id,
        )

        # Get all messages from the conversation
        conversation_messages = chat_manager_instance.get_messages(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        # Take cost snapshot before invoking
        cost_tracker = Config.get_cost_tracker()
        cost_snapshot = cost_tracker.get_snapshot()

        # Invoke the StateGraph
        result = _invoke_graph(conversation_messages, user_id, conversation_id)

        # Calculate and save cost delta
        cost_delta = cost_tracker.calculate_delta(cost_snapshot)
        if cost_delta.get("cost", 0) > 0 or cost_delta.get("calls", 0) > 0:
            chat_manager_instance.update_conversation_costs(
                cost_delta,
                conversation_id=conversation_id,
                user_id=user_id,
            )

        logger.debug(
            "Graph returned result for user=%s conversation=%s nodes=%s",
            user_id,
            conversation_id,
            result.get("nodes_executed", []),
        )

        if result:
            return _build_response_payload(result, user_id, conversation_id)

        return {"response": "No response available", "agentName": "supervisor"}
    except Exception as e:
        logger.exception(
            "Chat handler failed for user=%s conversation=%s",
            user_id,
            conversation_id,
        )
        raise HTTPException(status_code=500, detail=str(e))


# Supported audio MIME types
AUDIO_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
}

MAX_AUDIO_SIZE = 20 * 1024 * 1024


def _get_audio_mime_type(filename: str, content_type: str | None) -> str:
    """Determine the MIME type for an audio file."""
    if filename:
        ext = os.path.splitext(filename.lower())[1]
        if ext in AUDIO_MIME_TYPES:
            return AUDIO_MIME_TYPES[ext]
    if content_type and content_type.startswith("audio/"):
        return content_type
    return "audio/mpeg"


# ---------------------------------------------------------------------------
# Audio: combined transcription + intent classification prompt
# ---------------------------------------------------------------------------

_AUDIO_TRANSCRIBE_AND_CLASSIFY_PROMPT = """\
You will receive an audio clip. Perform TWO tasks:

1. **Transcribe** exactly what is being said.
2. **Classify** the user's intent into one of these categories:
   swap, lending, staking, dca, market_data, search, education, general

Return ONLY a JSON object (no markdown fences) with these fields:
{"transcription": "<exact transcription>", "intent": "<category>", "confidence": <0.0-1.0>}
"""

# Maps audio classification intents to agent runtime names
_AUDIO_INTENT_AGENT_MAP: Dict[str, str] = {
    "swap": "swap_agent",
    "lending": "lending_agent",
    "staking": "staking_agent",
    "dca": "dca_agent",
    "market_data": "crypto_agent",
    "search": "search_agent",
    "education": "default_agent",
    "general": "default_agent",
}


def _parse_audio_classification(raw_content: str) -> tuple[str, str | None, float]:
    """Parse the combined transcription + classification JSON response.

    Returns ``(transcription, intent, confidence)``.  Falls back gracefully
    if the model doesn't return valid JSON — treats the entire response as
    plain transcription.
    """
    text = raw_content.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        data = json.loads(text)
        transcription = (data.get("transcription") or "").strip()
        intent = (data.get("intent") or "").strip().lower()
        confidence = float(data.get("confidence", 0.0))

        if not transcription:
            # JSON parsed but no transcription field — use raw
            return raw_content.strip(), None, 0.0

        valid_intents = set(_AUDIO_INTENT_AGENT_MAP.keys())
        if intent not in valid_intents:
            intent = None
            confidence = 0.0

        return transcription, intent, confidence
    except (json.JSONDecodeError, ValueError, TypeError):
        # Not JSON — treat entire response as transcription
        return raw_content.strip(), None, 0.0


@app.post("/chat/audio")
async def chat_audio(
    audio: UploadFile = File(..., description="Audio file (mp3, wav, flac, ogg, webm, m4a)"),
    user_id: str = Form(..., description="User ID"),
    conversation_id: str = Form(..., description="Conversation ID"),
    wallet_address: str = Form("default", description="Wallet address"),
):
    """Process audio input through the agent pipeline.

    Optimisations over the naive sequential approach:
    1. Combined transcription + intent classification in a single LLM call
    2. Session setup + history fetch run in parallel with transcription
    3. All blocking calls run in a thread pool (asyncio.to_thread)
    4. Pre-classified intent is injected into graph state so semantic_router
       can skip the embedding call (~200 ms saved)
    """
    request_user_id: str | None = user_id
    request_conversation_id: str | None = conversation_id

    try:
        # Validate user_id
        if not user_id or user_id.lower() == "anonymous":
            wallet = (wallet_address or "").strip()
            if wallet and wallet.lower() != "default":
                request_user_id = f"wallet::{wallet.lower()}"
            else:
                raise HTTPException(
                    status_code=400,
                    detail="A stable 'user_id' or wallet_address is required.",
                )

        logger.debug(
            "Received audio chat request user=%s conversation=%s filename=%s",
            request_user_id,
            request_conversation_id,
            audio.filename,
        )

        # Validate file size
        audio_content = await audio.read()
        if len(audio_content) > MAX_AUDIO_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Audio file too large. Maximum size is {MAX_AUDIO_SIZE // (1024 * 1024)}MB.",
            )

        if len(audio_content) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty.")

        mime_type = _get_audio_mime_type(audio.filename or "", audio.content_type)
        logger.debug("Audio MIME type: %s, size: %d bytes", mime_type, len(audio_content))

        encoded_audio = base64.b64encode(audio_content).decode("utf-8")

        wallet = wallet_address.strip() if wallet_address else None
        if wallet and wallet.lower() == "default":
            wallet = None

        # Take cost snapshot
        cost_tracker = Config.get_cost_tracker()
        cost_snapshot = cost_tracker.get_snapshot()

        # ── Parallel phase: transcription + session/history ──────────────
        # These are independent — run concurrently.

        from src.llm.tiers import ModelTier
        llm = Config.get_llm(model=ModelTier.TRANSCRIPTION, with_cost_tracking=True)

        transcription_message = HumanMessage(
            content=[
                {"type": "text", "text": _AUDIO_TRANSCRIBE_AND_CLASSIFY_PROMPT},
                {"type": "media", "data": encoded_audio, "mime_type": mime_type},
            ]
        )

        async def _transcribe():
            return await asyncio.to_thread(llm.invoke, [transcription_message])

        async def _setup_session_and_history():
            await asyncio.to_thread(
                chat_manager_instance.ensure_session,
                request_user_id,
                request_conversation_id,
                wallet_address=wallet,
            )
            return await asyncio.to_thread(
                chat_manager_instance.get_messages,
                request_conversation_id,
                request_user_id,
            )

        transcription_response, conversation_messages = await asyncio.gather(
            _transcribe(),
            _setup_session_and_history(),
        )

        # ── Parse combined transcription + classification ────────────────

        raw_content = transcription_response.content
        if isinstance(raw_content, list):
            text_parts = []
            for part in raw_content:
                if isinstance(part, dict) and part.get("text"):
                    text_parts.append(part["text"])
                elif isinstance(part, str):
                    text_parts.append(part)
            raw_content = " ".join(text_parts).strip()

        transcribed_text, audio_intent, audio_confidence = _parse_audio_classification(
            raw_content or "",
        )

        if not transcribed_text:
            raise HTTPException(
                status_code=400,
                detail="Could not transcribe the audio. Please try again with a clearer recording.",
            )

        logger.info(
            "Audio transcribed: '%s' | intent=%s confidence=%.2f",
            transcribed_text[:200],
            audio_intent,
            audio_confidence,
        )

        # ── Store user message ───────────────────────────────────────────

        user_message = ChatMessage(
            role="user",
            content=transcribed_text,
            metadata={
                "source": "audio",
                "audio_filename": audio.filename,
                "audio_size": len(audio_content),
                "audio_mime_type": mime_type,
            },
        )
        await asyncio.to_thread(
            chat_manager_instance.add_message,
            user_message.dict(),
            request_conversation_id,
            request_user_id,
        )

        # Re-fetch messages with the newly added user message
        conversation_messages = await asyncio.to_thread(
            chat_manager_instance.get_messages,
            request_conversation_id,
            request_user_id,
        )

        # ── Invoke graph with pre-classified intent ──────────────────────

        pre_classified: Dict[str, Any] | None = None
        if audio_intent and audio_confidence > 0.0:
            pre_classified = {
                "route_intent": audio_intent,
                "route_confidence": audio_confidence,
                "route_agent": _AUDIO_INTENT_AGENT_MAP.get(audio_intent, "default_agent"),
            }

        result = await asyncio.to_thread(
            _invoke_graph,
            conversation_messages,
            request_user_id,
            request_conversation_id,
            pre_classified=pre_classified,
        )

        # ── Cost tracking ────────────────────────────────────────────────

        cost_delta = cost_tracker.calculate_delta(cost_snapshot)
        if cost_delta.get("cost", 0) > 0 or cost_delta.get("calls", 0) > 0:
            chat_manager_instance.update_conversation_costs(
                cost_delta,
                conversation_id=request_conversation_id,
                user_id=request_user_id,
            )

        logger.debug(
            "Graph returned result for audio user=%s conversation=%s nodes=%s",
            request_user_id,
            request_conversation_id,
            result.get("nodes_executed", []),
        )

        if result:
            return _build_response_payload(
                result,
                request_user_id,
                request_conversation_id,
                extra_fields={"transcription": transcribed_text},
            )

        return {
            "response": "No response available",
            "agentName": "supervisor",
            "transcription": transcribed_text,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Audio chat handler failed for user=%s conversation=%s",
            request_user_id,
            request_conversation_id,
        )
        raise HTTPException(status_code=500, detail=str(e))


# Include chat manager router
app.include_router(chat_manager_router)
