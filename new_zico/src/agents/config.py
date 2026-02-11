import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.llm import LLMFactory, CostTrackingCallback
from src.llm.tiers import ModelTier, model_for_agent

load_dotenv()

# Type alias for providers
Provider = Literal["google", "openai", "anthropic"]


class Config:
    """Application configuration with multi-provider LLM support."""

    # Default model configuration — gemini-2.5-flash everywhere
    DEFAULT_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gemini-2.5-flash")
    DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.7"))
    DEFAULT_PROVIDER: Provider = "google"

    # Embedding configuration
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")

    # Application configuration
    MAX_UPLOAD_LENGTH = 16 * 1024 * 1024
    MAX_CONVERSATION_LENGTH = 100
    MAX_CONTEXT_MESSAGES = 10

    # Agent configuration
    AGENTS_CONFIG = {
        "agents": [
            {
                "name": "crypto_data",
                "description": "Handles cryptocurrency-related queries",
                "type": "specialized",
                "enabled": True,
                "priority": 1,
            },
            {
                "name": "general",
                "description": "Handles general conversation and queries",
                "type": "general",
                "enabled": True,
                "priority": 2,
            },
        ]
    }

    # LangGraph configuration
    LANGGRAPH_CONFIG = {
        "max_iterations": 10,
        "timeout": 30,
        "memory_window": 10,
        "enable_memory": True,
    }

    # Conversation configuration
    CONVERSATION_CONFIG = {
        "default_user_id": "anonymous",
        "max_conversations_per_user": 50,
        "conversation_timeout_hours": 24,
        "enable_context_extraction": True,
    }

    # Instance caches
    _llm_instance: BaseChatModel | None = None
    _llm_fast_instance: BaseChatModel | None = None
    _embeddings_instance: GoogleGenerativeAIEmbeddings | None = None
    _cost_tracker: CostTrackingCallback | None = None

    @classmethod
    def get_llm(
        cls,
        model: str | None = None,
        temperature: float | None = None,
        with_cost_tracking: bool = True,
    ) -> BaseChatModel:
        model = model or cls.DEFAULT_MODEL
        temperature = temperature if temperature is not None else cls.DEFAULT_TEMPERATURE

        use_cache = model == cls.DEFAULT_MODEL and temperature == cls.DEFAULT_TEMPERATURE

        if use_cache and cls._llm_instance is not None:
            return cls._llm_instance

        callbacks = []
        if with_cost_tracking:
            callbacks.append(cls.get_cost_tracker())

        llm = LLMFactory.create(
            model=model,
            temperature=temperature,
            callbacks=callbacks if callbacks else None,
            use_cache=False,
        )

        if use_cache:
            cls._llm_instance = llm

        return llm

    @classmethod
    def get_fast_llm(cls, with_cost_tracking: bool = True) -> BaseChatModel:
        """Return a cached FAST-tier LLM (gemini-2.5-flash)."""
        if cls._llm_fast_instance is not None:
            return cls._llm_fast_instance

        callbacks = []
        if with_cost_tracking:
            callbacks.append(cls.get_cost_tracker())

        llm = LLMFactory.create(
            model=ModelTier.FAST,
            temperature=cls.DEFAULT_TEMPERATURE,
            callbacks=callbacks if callbacks else None,
            use_cache=False,
        )
        cls._llm_fast_instance = llm
        return llm

    @classmethod
    def get_llm_for_agent(
        cls,
        agent_name: str,
        with_cost_tracking: bool = True,
    ) -> BaseChatModel:
        """Return the optimal LLM for *agent_name* based on its tier."""
        model = model_for_agent(agent_name)
        if model == ModelTier.FAST:
            return cls.get_fast_llm(with_cost_tracking=with_cost_tracking)
        return cls.get_llm(model=model, with_cost_tracking=with_cost_tracking)

    @classmethod
    def get_embeddings(cls) -> GoogleGenerativeAIEmbeddings:
        """Get or create embeddings instance (singleton)."""
        if cls._embeddings_instance is None:
            cls._embeddings_instance = GoogleGenerativeAIEmbeddings(
                model=cls.EMBEDDING_MODEL,
                google_api_key=os.getenv("GEMINI_API_KEY"),
            )
        return cls._embeddings_instance

    @classmethod
    def get_cost_tracker(cls) -> CostTrackingCallback:
        """Get or create cost tracker instance (singleton)."""
        if cls._cost_tracker is None:
            cls._cost_tracker = CostTrackingCallback(log_calls=True)
        return cls._cost_tracker

    @classmethod
    def get_agent_config(cls, agent_name: str) -> dict | None:
        for agent in cls.AGENTS_CONFIG["agents"]:
            if agent["name"] == agent_name:
                return agent
        return None

    @classmethod
    def get_enabled_agents(cls) -> list[dict]:
        return [
            agent
            for agent in cls.AGENTS_CONFIG["agents"]
            if agent.get("enabled", True)
        ]

    @classmethod
    def list_available_models(cls) -> list[str]:
        return LLMFactory.list_models()

    @classmethod
    def list_available_providers(cls) -> list[str]:
        return LLMFactory.list_providers()

    @classmethod
    def validate_config(cls) -> bool:
        try:
            llm = cls.get_llm(with_cost_tracking=False)
            embeddings = cls.get_embeddings()
            return True
        except Exception as e:
            print(f"Configuration validation failed: {e}")
            return False

    @classmethod
    def reset_instances(cls) -> None:
        cls._llm_instance = None
        cls._llm_fast_instance = None
        cls._embeddings_instance = None
        if cls._cost_tracker:
            cls._cost_tracker.reset()
        LLMFactory.clear_cache()
