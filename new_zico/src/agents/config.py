import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.llm import LLMFactory, CostTrackingCallback

load_dotenv()

# Type alias for providers
Provider = Literal["google", "openai", "anthropic"]


class Config:
    """Application configuration with multi-provider LLM support."""

    # Default model configuration
    DEFAULT_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gemini-3-flash-preview") # gemini-3-pro-preview
    DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.7"))
    DEFAULT_PROVIDER: Provider = "google"

    # Embedding configuration
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/embedding-001")

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
    _embeddings_instance: GoogleGenerativeAIEmbeddings | None = None
    _cost_tracker: CostTrackingCallback | None = None

    @classmethod
    def get_llm(
        cls,
        model: str | None = None,
        temperature: float | None = None,
        with_cost_tracking: bool = True,
    ) -> BaseChatModel:
        """
        Get or create LLM instance using the factory.

        Args:
            model: Model name (defaults to DEFAULT_MODEL)
            temperature: Sampling temperature (defaults to DEFAULT_TEMPERATURE)
            with_cost_tracking: Whether to attach cost tracking callback

        Returns:
            BaseChatModel instance
        """
        model = model or cls.DEFAULT_MODEL
        temperature = temperature if temperature is not None else cls.DEFAULT_TEMPERATURE

        # Use cache for default config
        use_cache = model == cls.DEFAULT_MODEL and temperature == cls.DEFAULT_TEMPERATURE

        if use_cache and cls._llm_instance is not None:
            return cls._llm_instance

        # Build callbacks
        callbacks = []
        if with_cost_tracking:
            callbacks.append(cls.get_cost_tracker())

        llm = LLMFactory.create(
            model=model,
            temperature=temperature,
            callbacks=callbacks if callbacks else None,
            use_cache=False,  # We handle caching ourselves
        )

        if use_cache:
            cls._llm_instance = llm

        return llm

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
        """Get configuration for a specific agent."""
        for agent in cls.AGENTS_CONFIG["agents"]:
            if agent["name"] == agent_name:
                return agent
        return None

    @classmethod
    def get_enabled_agents(cls) -> list[dict]:
        """Get list of enabled agents."""
        return [
            agent
            for agent in cls.AGENTS_CONFIG["agents"]
            if agent.get("enabled", True)
        ]

    @classmethod
    def list_available_models(cls) -> list[str]:
        """List all available LLM models."""
        return LLMFactory.list_models()

    @classmethod
    def list_available_providers(cls) -> list[str]:
        """List all available LLM providers."""
        return LLMFactory.list_providers()

    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration by testing connections."""
        try:
            llm = cls.get_llm(with_cost_tracking=False)
            embeddings = cls.get_embeddings()
            return True
        except Exception as e:
            print(f"Configuration validation failed: {e}")
            return False

    @classmethod
    def reset_instances(cls) -> None:
        """Reset all cached instances."""
        cls._llm_instance = None
        cls._embeddings_instance = None
        if cls._cost_tracker:
            cls._cost_tracker.reset()
        LLMFactory.clear_cache()