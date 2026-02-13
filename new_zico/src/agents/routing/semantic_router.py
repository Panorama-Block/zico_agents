"""
Semantic Router — embedding-based intent classification.

Replaces keyword matching with cosine-similarity against pre-computed
exemplar embeddings.  Latency target: < 100 ms per classification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent taxonomy
# ---------------------------------------------------------------------------

class IntentCategory(str, Enum):
    SWAP = "swap"
    LENDING = "lending"
    STAKING = "staking"
    DCA = "dca"
    MARKET_DATA = "market_data"
    PORTFOLIO = "portfolio"
    EDUCATION = "education"
    SEARCH = "search"
    GENERAL = "general"


# Maps intents to agent runtime names.
_INTENT_AGENT_MAP: Dict[IntentCategory, str] = {
    IntentCategory.SWAP: "swap_agent",
    IntentCategory.LENDING: "lending_agent",
    IntentCategory.STAKING: "staking_agent",
    IntentCategory.DCA: "dca_agent",
    IntentCategory.MARKET_DATA: "crypto_agent",
    IntentCategory.PORTFOLIO: "portfolio_advisor",
    IntentCategory.EDUCATION: "default_agent",
    IntentCategory.SEARCH: "search_agent",
    IntentCategory.GENERAL: "default_agent",
}


@dataclass(frozen=True)
class RouteDecision:
    intent: IntentCategory
    confidence: float
    agent_name: str
    needs_llm_confirmation: bool  # True when confidence < high-threshold


# ---------------------------------------------------------------------------
# Few-shot exemplars (anchors for each intent)
# ---------------------------------------------------------------------------

INTENT_EXEMPLARS: Dict[IntentCategory, List[str]] = {
    IntentCategory.SWAP: [
        "I want to swap 100 USDC for ETH on Avalanche",
        "Exchange my AVAX for USDC",
        "Convert 50 WBTC to ETH on Arbitrum",
        "Trade my tokens on Base",
        "Swap USDC to SOL on Base",
        "I'd like to exchange some tokens",
        "Can I trade ETH for USDC?",
        "Swap 0.5 ETH to USDC on Ethereum",
        "I want to make a swap",
        "Troque 500 USDC por SOL na rede Base",
    ],
    IntentCategory.LENDING: [
        "Supply 1000 USDC on Aave",
        "I want to borrow ETH on Arbitrum",
        "Repay my USDC loan",
        "Withdraw my WETH from Aave",
        "I want to deposit 500 DAI",
        "Help me with a lending operation",
        "I want to make a supply of 100 USDC",
        "Borrow some WETH on Polygon",
        "I want to lend my tokens",
        "Withdraw my assets from the lending protocol",
    ],
    IntentCategory.STAKING: [
        "Stake 2 ETH on Lido",
        "I want to earn staking rewards",
        "Unstake my stETH",
        "Convert ETH to stETH",
        "I want to stake some ETH",
        "Help me unstake my stETH back to ETH",
        "How much can I earn from staking?",
        "I want to do liquid staking",
        "Stake ETH for stETH rewards",
    ],
    IntentCategory.DCA: [
        "Help me schedule a daily DCA from USDC to AVAX",
        "Suggest a weekly swap DCA strategy",
        "I want to automate a monthly swap from USDC to ETH",
        "Set up dollar cost averaging for BTC",
        "Plan a DCA strategy for me",
        "I want to buy ETH every week automatically",
        "Create a recurring buy plan",
    ],
    IntentCategory.MARKET_DATA: [
        "What is the price of Bitcoin?",
        "Show me the TVL of Uniswap",
        "What's the market cap of Ethereum?",
        "Floor price of Bored Apes",
        "How much is SOL right now?",
        "What's the FDV of Aave?",
        "Get me the price of AVAX",
        "Current ETH price",
        "Bitcoin market cap",
        "What is the TVL of Avalanche?",
    ],
    IntentCategory.PORTFOLIO: [
        "Analyze my portfolio",
        "What's my biggest risk?",
        "How should I rebalance my wallet?",
        "Show me my token holdings",
        "What tokens do I have?",
        "Am I too exposed to any single token?",
        "Give me a risk assessment of my wallet",
        "How diversified is my portfolio?",
        "What should I do with my tokens?",
        "What is the amount of each token?",
        "How much of each token do I hold?",
        "Show me the value of each position",
        "List all my tokens with balances",
        "Where am I most exposed?",
        "Which tokens should I sell?",
        "Where should I take more risk?",
        "Where should I be more careful?",
        "Is my wallet safe?",
        "Analise minha carteira",
        "Qual meu maior risco?",
        "Como balancear minha carteira?",
        "Quais tokens eu tenho?",
        "Quanto tenho de cada token?",
        "Onde posso arriscar mais?",
    ],
    IntentCategory.EDUCATION: [
        "What is DeFi?",
        "How does liquid staking work?",
        "Explain impermanent loss",
        "What are the best pools on Trader Joe?",
        "What is a liquidity pool?",
        "How do AMMs work?",
        "Explain yield farming",
        "What is the difference between staking and lending?",
        "What are gas fees?",
        "How does a DEX work?",
    ],
    IntentCategory.SEARCH: [
        "What happened with Bitcoin this week?",
        "Latest Avalanche ecosystem news",
        "Who just won the Formula 1 race?",
        "Find the latest crypto regulations",
        "Search for recent Ethereum updates",
        "What are the trending topics in crypto today?",
        "News about Solana",
    ],
    IntentCategory.GENERAL: [
        "Hello, how are you?",
        "Tell me a joke",
        "What can you do?",
        "Who are you?",
        "Thanks for the help",
        "Goodbye",
        "Help me",
    ],
}


# ---------------------------------------------------------------------------
# Router implementation
# ---------------------------------------------------------------------------

class SemanticRouter:
    """Classify user intents via embedding cosine similarity."""

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.78   # Route directly, no LLM confirmation needed
    LOW_CONFIDENCE = 0.50    # Below this → fall through to supervisor graph

    def __init__(self, embeddings_model) -> None:
        self._embeddings = embeddings_model
        self._exemplar_vectors: Dict[IntentCategory, np.ndarray] = {}
        self._ready = False

    # ---- Lifecycle ---------------------------------------------------------

    def warm_up(self) -> None:
        """Pre-compute exemplar embeddings.  Call once at startup."""
        if self._ready:
            return
        try:
            for intent, examples in INTENT_EXEMPLARS.items():
                vectors = self._embeddings.embed_documents(examples)
                self._exemplar_vectors[intent] = np.array(vectors)
            self._ready = True
            logger.info(
                "SemanticRouter warmed up: %d intents, %d total exemplars",
                len(self._exemplar_vectors),
                sum(len(v) for v in INTENT_EXEMPLARS.values()),
            )
        except Exception:
            logger.exception("SemanticRouter warm-up failed; falling back to GENERAL.")
            self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ---- Classification ----------------------------------------------------

    def classify(
        self,
        user_message: str,
        high_threshold: float | None = None,
    ) -> RouteDecision:
        """
        Classify *user_message* and return a ``RouteDecision``.

        Falls back to ``GENERAL`` if embeddings are unavailable.
        """
        if not self._ready:
            return RouteDecision(
                intent=IntentCategory.GENERAL,
                confidence=0.0,
                agent_name="default_agent",
                needs_llm_confirmation=True,
            )

        threshold = high_threshold or self.HIGH_CONFIDENCE

        try:
            query_vec = np.array(self._embeddings.embed_query(user_message))
            # Normalise for cosine similarity
            query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)

            best_intent = IntentCategory.GENERAL
            best_score = 0.0

            for intent, exemplar_matrix in self._exemplar_vectors.items():
                # Normalise rows
                norms = np.linalg.norm(exemplar_matrix, axis=1, keepdims=True) + 1e-10
                normed = exemplar_matrix / norms
                similarities = normed @ query_norm
                max_sim = float(np.max(similarities))
                if max_sim > best_score:
                    best_score = max_sim
                    best_intent = intent

            agent_name = _INTENT_AGENT_MAP.get(best_intent, "default_agent")

            return RouteDecision(
                intent=best_intent,
                confidence=best_score,
                agent_name=agent_name,
                needs_llm_confirmation=best_score < threshold,
            )
        except Exception:
            logger.exception("SemanticRouter.classify failed; defaulting to GENERAL.")
            return RouteDecision(
                intent=IntentCategory.GENERAL,
                confidence=0.0,
                agent_name="default_agent",
                needs_llm_confirmation=True,
            )
