"""Lightweight RAG wrapper for DCA strategy documents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

REGISTRY_PATH = Path(__file__).resolve().parent / "strategy_registry.json"


def _load_registry(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


@dataclass(slots=True)
class StrategyDocument:
    strategy_id: str
    version: str
    name: str
    description: str
    tokens_supported: List[Dict[str, Sequence[str]]]
    cadence_options: List[str]
    amount_bounds: Dict[str, Any]
    slippage_bps: Dict[str, Any]
    risk_tier: str
    defaults: Dict[str, Any] = field(default_factory=dict)
    guardrails: List[str] = field(default_factory=list)
    compliance_notes: List[str] = field(default_factory=list)
    context: str = ""

    def embed_text(self) -> str:
        tokens_text = " ".join(
            f"from:{'|'.join(entry.get('from', []))} to:{'|'.join(entry.get('to', []))}"
            for entry in self.tokens_supported
        )
        guardrails = " ".join(self.guardrails)
        compliance = " ".join(self.compliance_notes)
        cadence = " ".join(self.cadence_options)
        defaults_text = " ".join(f"{key}:{value}" for key, value in self.defaults.items())
        return " ".join(
            [
                self.name,
                self.description,
                self.context,
                tokens_text,
                cadence,
                self.risk_tier,
                guardrails,
                compliance,
                defaults_text,
            ]
        )

    def to_consulting_payload(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "name": self.name,
            "summary": self.description,
            "context": self.context,
            "defaults": self.defaults,
            "guardrails": self.guardrails,
            "compliance_notes": self.compliance_notes,
            "cadence_options": self.cadence_options,
            "amount_bounds": self.amount_bounds,
            "slippage_bps": self.slippage_bps,
            "risk_tier": self.risk_tier,
            "tokens_supported": self.tokens_supported,
        }


@dataclass(slots=True)
class StrategyMatch:
    document: StrategyDocument
    confidence: float
    highlights: List[str] = field(default_factory=list)

    def to_payload(self) -> Dict[str, Any]:
        payload = self.document.to_consulting_payload()
        payload["confidence"] = self.confidence
        if self.highlights:
            payload["highlights"] = self.highlights
        return payload


class StrategyRetriever:
    """Simple TF-IDF backed retrieval to simulate strategy RAG behaviour."""

    def __init__(
        self,
        *,
        registry_path: Path | None = None,
        min_score: float = 0.18,
    ) -> None:
        self._registry_path = registry_path or REGISTRY_PATH
        self._min_score = min_score
        self._documents: List[StrategyDocument] = [
            StrategyDocument(**entry) for entry in _load_registry(self._registry_path)
        ]
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._matrix = None
        if self._documents:
            self._vectorizer = TfidfVectorizer()
            corpus = [doc.embed_text() for doc in self._documents]
            self._matrix = self._vectorizer.fit_transform(corpus)

    def refresh(self) -> None:
        """Reload the registry and refresh embeddings."""

        self._documents = [StrategyDocument(**entry) for entry in _load_registry(self._registry_path)]
        if not self._documents:
            self._vectorizer = None
            self._matrix = None
            return
        self._vectorizer = TfidfVectorizer()
        corpus = [doc.embed_text() for doc in self._documents]
        self._matrix = self._vectorizer.fit_transform(corpus)

    def is_ready(self) -> bool:
        return bool(self._vectorizer) and self._matrix is not None

    def search(
        self,
        *,
        from_token: str | None = None,
        to_token: str | None = None,
        cadence: str | None = None,
        risk_tier: str | None = None,
        text: str | None = None,
        top_k: int = 3,
    ) -> List[StrategyMatch]:
        if not self.is_ready():
            return []

        query_terms: List[str] = []
        if from_token:
            query_terms.append(f"from:{from_token}")
        if to_token:
            query_terms.append(f"to:{to_token}")
        if cadence:
            query_terms.append(f"cadence:{cadence}")
        if risk_tier:
            query_terms.append(f"risk:{risk_tier}")
        if text:
            query_terms.append(text)

        if not query_terms:
            return []

        query = " ".join(query_terms)
        vector = self._vectorizer.transform([query])
        scores = cosine_similarity(vector, self._matrix)[0]

        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        matches: List[StrategyMatch] = []
        for idx, score in ranked[:top_k]:
            if score < self._min_score:
                continue
            doc = self._documents[idx]
            highlights = self._build_highlights(doc, from_token, to_token, cadence)
            matches.append(StrategyMatch(document=doc, confidence=float(round(score, 4)), highlights=highlights))
        return matches

    @staticmethod
    def _build_highlights(
        doc: StrategyDocument,
        from_token: str | None,
        to_token: str | None,
        cadence: str | None,
    ) -> List[str]:
        highlights: List[str] = []
        if from_token and any(from_token.upper() in map(str.upper, entry.get("from", [])) for entry in doc.tokens_supported):
            highlights.append(f"Supports funding token {from_token}.")
        if to_token and any(to_token.upper() in map(str.upper, entry.get("to", [])) for entry in doc.tokens_supported):
            highlights.append(f"Supports target token {to_token}.")
        if cadence and cadence.lower() in {option.lower() for option in doc.cadence_options}:
            highlights.append(f"Includes {cadence} cadence.")
        return highlights


_retriever = StrategyRetriever()


def get_strategy_retriever() -> StrategyRetriever:
    if not _retriever.is_ready():
        _retriever.refresh()
    return _retriever
