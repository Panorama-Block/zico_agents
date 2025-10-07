import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logging.info("Test log from app.py startup")
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import re

from src.agents.config import Config
from src.agents.supervisor.agent import Supervisor
from src.models.chatMessage import ChatMessage
from src.routes.chat_manager_routes import router as chat_manager_router
from src.service.chat_manager import chat_manager_instance
from src.agents.crypto_data.tools import get_coingecko_id, get_tradingview_symbol
from src.agents.metadata import metadata

# Initialize FastAPI app
app = FastAPI(title="Zico Agent API", version="1.0")

# Enable CORS for local/frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Supervisor agent (singleton LLM)
supervisor = Supervisor(Config.get_llm())

class ChatRequest(BaseModel):
    message: ChatMessage
    chain_id: str = "default"
    wallet_address: str = "default"
    conversation_id: str = "default"
    user_id: str = "anonymous"

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
    # Validate provided names against available agents
    available_names = {a["name"] for a in AVAILABLE_AGENTS}
    valid_agents = [a for a in agents if a in available_names]
    if not valid_agents:
        # Keep previous selection if nothing valid provided
        return {"status": "no_change", "agents": SELECTED_AGENTS}
    # Update selection
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
        "supervisor": "supervisor",
    }
    return mapping.get(agent_name, "supervisor")

@app.get("/health")
def health_check():
    return {"status": "ok"}

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
    print("request: ", request)
    try:
        # Add the user message to the conversation
        chat_manager_instance.add_message(
            message=request.message.dict(),
            conversation_id=request.conversation_id,
            user_id=request.user_id
        )
        
        # Get all messages from the conversation to pass to the agent
        conversation_messages = chat_manager_instance.get_messages(
            conversation_id=request.conversation_id,
            user_id=request.user_id
        )
        
        # Invoke the supervisor agent with the conversation
        result = supervisor.invoke(conversation_messages)
        
        # Add the agent's response to the conversation
        if result and isinstance(result, dict):
            print("result: ", result)
            agent_name = result.get("agent", "supervisor")
            print("agent_name: ", agent_name)
            agent_name = _map_agent_type(agent_name)

            # Build response metadata and enrich with coin info for crypto price queries
            response_metadata = {"supervisor_result": result}
            swap_meta_snapshot = None
            # Prefer supervisor-provided metadata
            if isinstance(result, dict) and result.get("metadata"):
                response_metadata.update(result.get("metadata") or {})
            elif agent_name == "token swap":
                swap_meta = metadata.get_swap_agent()
                if swap_meta:
                    response_metadata.update(swap_meta)
                    swap_meta_snapshot = swap_meta
            print("response_metadata: ", response_metadata)
            
            # Create a ChatMessage from the supervisor response
            response_message = ChatMessage(
                role="assistant",
                content=result.get("response", "No response available"),
                agent_name=agent_name,
                agent_type=_map_agent_type(agent_name),
                metadata=result.get("metadata", {}),
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                requires_action=True if agent_name == "token swap" else False,
                action_type="swap" if agent_name == "token swap" else None
            )
            
            # Add the response message to the conversation
            chat_manager_instance.add_message(
                message=response_message.dict(),
                conversation_id=request.conversation_id,
                user_id=request.user_id
            )

            # Return only the clean response
            response_payload = {
                "response": result.get("response", "No response available"),
                "agentName": agent_name,
            }
            response_meta = result.get("metadata") or {}
            if agent_name == "token swap" and not response_meta:
                if swap_meta_snapshot:
                    response_meta = swap_meta_snapshot
                else:
                    swap_meta = metadata.get_swap_agent()
                    if swap_meta:
                        response_meta = swap_meta
                    metadata.set_swap_agent({})
            if response_meta:
                response_payload["metadata"] = response_meta
            if agent_name == "token swap":
                metadata.set_swap_agent({})
            return response_payload
        
        return {"response": "No response available", "agent": "supervisor"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include chat manager router
app.include_router(chat_manager_router)
