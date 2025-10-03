import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from typing import Optional

load_dotenv()

gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY não encontrada nas variáveis de ambiente")

class Config:
    # Model configuration
    GEMINI_MODEL = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL = "models/embedding-001"
    GEMINI_API_KEY = gemini_api_key
    
    # Application configuration
    MAX_UPLOAD_LENGTH = 16 * 1024 * 1024
    MAX_CONVERSATION_LENGTH = 100  # Maximum messages per conversation
    MAX_CONTEXT_MESSAGES = 10  # Maximum messages to include in context
    
    # Agent configuration
    AGENTS_CONFIG = {
        "agents": [
            {
                "name": "crypto_data",
                "description": "Handles cryptocurrency-related queries",
                "type": "specialized",
                "enabled": True,
                "priority": 1
            },
            {
                "name": "general",
                "description": "Handles general conversation and queries",
                "type": "general",
                "enabled": True,
                "priority": 2
            }
        ]
    }
    
    # LangGraph configuration
    LANGGRAPH_CONFIG = {
        "max_iterations": 10,
        "timeout": 30,
        "memory_window": 10,
        "enable_memory": True
    }
    
    # Conversation configuration
    CONVERSATION_CONFIG = {
        "default_user_id": "anonymous",
        "max_conversations_per_user": 50,
        "conversation_timeout_hours": 24,
        "enable_context_extraction": True
    }
    
    # LLM instances (singleton pattern)
    _llm_instance: Optional[ChatGoogleGenerativeAI] = None
    _embeddings_instance: Optional[GoogleGenerativeAIEmbeddings] = None
    
    @classmethod
    def get_llm(cls) -> ChatGoogleGenerativeAI:
        """Get or create LLM instance (singleton)"""
        if cls._llm_instance is None:
            cls._llm_instance = ChatGoogleGenerativeAI(
                model=cls.GEMINI_MODEL,
                temperature=0.7,
                google_api_key=cls.GEMINI_API_KEY
            )
        return cls._llm_instance
    
    @classmethod
    def get_embeddings(cls) -> GoogleGenerativeAIEmbeddings:
        """Get or create embeddings instance (singleton)"""
        if cls._embeddings_instance is None:
            cls._embeddings_instance = GoogleGenerativeAIEmbeddings(
                model=cls.GEMINI_EMBEDDING_MODEL,
                google_api_key=cls.GEMINI_API_KEY
            )
        return cls._embeddings_instance
    
    @classmethod
    def get_agent_config(cls, agent_name: str) -> Optional[dict]:
        """Get configuration for a specific agent"""
        for agent in cls.AGENTS_CONFIG["agents"]:
            if agent["name"] == agent_name:
                return agent
        return None
    
    @classmethod
    def get_enabled_agents(cls) -> list:
        """Get list of enabled agents"""
        return [
            agent for agent in cls.AGENTS_CONFIG["agents"] 
            if agent.get("enabled", True)
        ]
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration"""
        try:
            # Test LLM connection
            llm = cls.get_llm()
            # Test embeddings connection
            embeddings = cls.get_embeddings()
            return True
        except Exception as e:
            print(f"Configuration validation failed: {e}")
            return False