import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logging.info("Test log from app.py startup")
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from src.agents.config import Config
from src.agents.supervisor.agent import Supervisor
from src.models.chatMessage import ChatMessage
from src.routes.chat_manager_routes import router as chat_manager_router
from src.service.chat_manager import chat_manager_instance

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
    conversation_id: str = "default"
    user_id: str = "anonymous"

@app.get("/health")
def health_check():
    return {"status": "ok"}

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
            # Create a ChatMessage from the supervisor response
            response_message = ChatMessage(
                role="assistant",
                content=result.get("response", "No response available"),
                agent_name=result.get("agent", "supervisor"),
                agent_type="supervisor",
                metadata={"supervisor_result": result},
                conversation_id=request.conversation_id,
                user_id=request.user_id
            )
            
            # Add the response message to the conversation
            chat_manager_instance.add_message(
                message=response_message.dict(),
                conversation_id=request.conversation_id,
                user_id=request.user_id
            )
            
            # Return only the clean response
            return {
                "response": result.get("response", "No response available"),
                "agent": result.get("agent", "supervisor")
            }
        
        return {"response": "No response available", "agent": "supervisor"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include chat manager router
app.include_router(chat_manager_router)
