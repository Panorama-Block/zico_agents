"""
Cost Tracking Callback for LLM usage monitoring.

Tracks token usage and calculates costs per LLM call.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class CostTrackingCallback(BaseCallbackHandler):
    """
    LangChain callback handler for tracking LLM costs.

    Tracks:
    - Input/output token counts
    - Cost per call and cumulative
    - Model usage statistics

    Usage:
        callback = CostTrackingCallback()
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", callbacks=[callback])
        response = llm.invoke("Hello!")
        print(callback.get_summary())
    """

    # Pricing per 1M tokens (USD) - Update as needed
    PRICING: dict[str, dict[str, float]] = {
        # Google Gemini
        "gemini-3-pro-preview": {"input": 1.50, "output": 6.00, "cache": 0.40},
        "gemini-2.5-flash": {"input": 0.15, "output": 0.60, "cache": 0.02},
        "gemini-2.5-pro": {"input": 1.25, "output": 5.00, "cache": 0.32},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "cache": 0.01},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "cache": 0.02},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00, "cache": 0.32},
        # OpenAI
        "gpt-4o": {"input": 2.50, "output": 10.00, "cache": 1.25},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cache": 0.08},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00, "cache": 5.00},
        "gpt-4": {"input": 30.00, "output": 60.00, "cache": 15.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50, "cache": 0.25},
        # Anthropic Claude
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00, "cache": 0.30},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00, "cache": 0.30},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00, "cache": 0.08},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00, "cache": 1.50},
    }

    # Default pricing for unknown models
    DEFAULT_PRICING = {"input": 1.00, "output": 3.00, "cache": 0.10}

    def __init__(self, log_calls: bool = True):
        """
        Initialize the cost tracker.

        Args:
            log_calls: Whether to log each LLM call
        """
        super().__init__()
        self.log_calls = log_calls
        self.total_cost: float = 0.0
        self.total_tokens: dict[str, int] = {"input": 0, "output": 0, "cache": 0}
        self.calls: list[dict[str, Any]] = []
        self.start_time: datetime = datetime.utcnow()

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs) -> None:
        """Called when LLM starts processing."""
        pass  # Could track start time per call if needed

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """
        Called when LLM finishes processing.

        Calculates and records the cost of the call.
        """
        logger.debug(f"[COST DEBUG] on_llm_end called. llm_output: {response.llm_output}")

        # Try to extract usage from multiple sources (different providers put it in different places)
        input_tokens = 0
        output_tokens = 0
        cache_tokens = 0
        model = "unknown"

        # Source 1: llm_output (OpenAI, Anthropic style)
        if response.llm_output:
            model = self._extract_model_name(response.llm_output)
            usage = response.llm_output.get("token_usage", {})
            input_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
            cache_tokens = usage.get("cache_read_input_tokens", 0) or usage.get("cached_tokens", 0)

        # Source 2: generations metadata (Google Gemini style)
        if input_tokens == 0 and output_tokens == 0 and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    # Check generation_info
                    gen_info = getattr(gen, "generation_info", {}) or {}
                    usage_meta = gen_info.get("usage_metadata", {})
                    if usage_meta:
                        input_tokens = usage_meta.get("input_tokens", 0)
                        output_tokens = usage_meta.get("output_tokens", 0)
                        cache_details = usage_meta.get("input_token_details", {})
                        cache_tokens = cache_details.get("cache_read", 0)
                        if model == "unknown":
                            model = gen_info.get("model_name", "unknown")
                        break

                    # Check message attribute (for ChatGeneration)
                    msg = getattr(gen, "message", None)
                    if msg:
                        msg_usage = getattr(msg, "usage_metadata", None)
                        if msg_usage:
                            input_tokens = msg_usage.get("input_tokens", 0)
                            output_tokens = msg_usage.get("output_tokens", 0)
                            cache_details = msg_usage.get("input_token_details", {})
                            cache_tokens = cache_details.get("cache_read", 0)
                            resp_meta = getattr(msg, "response_metadata", {}) or {}
                            if model == "unknown":
                                model = resp_meta.get("model_name", "unknown")
                            break
                if input_tokens > 0 or output_tokens > 0:
                    break

        # Skip if no usage data found
        if input_tokens == 0 and output_tokens == 0:
            logger.debug("[COST DEBUG] No token usage found in response, skipping cost tracking")
            return

        logger.debug(f"[COST DEBUG] Extracted: model={model}, input={input_tokens}, output={output_tokens}, cache={cache_tokens}")

        # Calculate cost
        pricing = self.PRICING.get(model, self.DEFAULT_PRICING)
        input_cost = (input_tokens * pricing["input"]) / 1_000_000
        output_cost = (output_tokens * pricing["output"]) / 1_000_000
        cache_cost = (cache_tokens * pricing["cache"]) / 1_000_000
        total_call_cost = input_cost + output_cost + cache_cost

        # Update totals
        self.total_cost += total_call_cost
        self.total_tokens["input"] += input_tokens
        self.total_tokens["output"] += output_tokens
        self.total_tokens["cache"] += cache_tokens

        # Record call details
        call_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "cache": cache_tokens,
            },
            "cost": {
                "input": input_cost,
                "output": output_cost,
                "cache": cache_cost,
                "total": total_call_cost,
            },
        }
        self.calls.append(call_info)

        # Log if enabled
        if self.log_calls:
            logger.info(
                f"[COST] {model} | "
                f"Tokens: {input_tokens:,} in / {output_tokens:,} out"
                + (f" / {cache_tokens:,} cache" if cache_tokens else "")
                + f" | Cost: ${total_call_cost:.6f} | Total: ${self.total_cost:.6f}"
            )

    def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Called when LLM encounters an error."""
        logger.error(f"[COST] LLM Error: {error}")

    def _extract_model_name(self, llm_output: dict[str, Any]) -> str:
        """Extract model name from LLM output."""
        # Try common keys
        for key in ["model_name", "model", "model_id"]:
            if key in llm_output:
                return llm_output[key]

        # Check nested structure
        if "model_info" in llm_output:
            return llm_output["model_info"].get("model", "unknown")

        return "unknown"

    def get_summary(self) -> dict[str, Any]:
        """
        Get a summary of all tracked costs.

        Returns:
            Dictionary with cost summary
        """
        duration = (datetime.utcnow() - self.start_time).total_seconds()

        return {
            "total_cost": round(self.total_cost, 6),
            "total_tokens": self.total_tokens.copy(),
            "calls_count": len(self.calls),
            "duration_seconds": round(duration, 2),
            "avg_cost_per_call": round(self.total_cost / len(self.calls), 6) if self.calls else 0,
            "models_used": list(set(call["model"] for call in self.calls)),
            "start_time": self.start_time.isoformat(),
        }

    def get_detailed_report(self) -> dict[str, Any]:
        """
        Get a detailed report including all calls.

        Returns:
            Dictionary with full cost details
        """
        summary = self.get_summary()
        summary["calls"] = self.calls
        return summary

    def get_cost_by_model(self) -> dict[str, dict[str, float]]:
        """
        Get costs aggregated by model.

        Returns:
            Dictionary mapping model names to their costs
        """
        by_model: dict[str, dict[str, float]] = {}

        for call in self.calls:
            model = call["model"]
            if model not in by_model:
                by_model[model] = {"cost": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}

            by_model[model]["cost"] += call["cost"]["total"]
            by_model[model]["input_tokens"] += call["tokens"]["input"]
            by_model[model]["output_tokens"] += call["tokens"]["output"]
            by_model[model]["calls"] += 1

        return by_model

    def reset(self) -> None:
        """Reset all tracked data."""
        self.total_cost = 0.0
        self.total_tokens = {"input": 0, "output": 0, "cache": 0}
        self.calls = []
        self.start_time = datetime.utcnow()

    def get_snapshot(self) -> dict[str, Any]:
        """
        Get a snapshot of current totals for delta calculation.

        Returns:
            Dictionary with current cost and token totals
        """
        return {
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens.copy(),
            "calls_count": len(self.calls),
        }

    def calculate_delta(self, previous_snapshot: dict[str, Any]) -> dict[str, Any]:
        """
        Calculate the delta between current state and a previous snapshot.

        Args:
            previous_snapshot: Snapshot from get_snapshot()

        Returns:
            Dictionary with cost and token deltas for this period
        """
        prev_cost = previous_snapshot.get("total_cost", 0.0)
        prev_tokens = previous_snapshot.get("total_tokens", {"input": 0, "output": 0, "cache": 0})
        prev_calls = previous_snapshot.get("calls_count", 0)

        return {
            "cost": round(self.total_cost - prev_cost, 6),
            "tokens": {
                "input": self.total_tokens["input"] - prev_tokens.get("input", 0),
                "output": self.total_tokens["output"] - prev_tokens.get("output", 0),
                "cache": self.total_tokens["cache"] - prev_tokens.get("cache", 0),
            },
            "calls": len(self.calls) - prev_calls,
        }

    def __str__(self) -> str:
        """String representation of current costs."""
        return (
            f"CostTracker: ${self.total_cost:.6f} total | "
            f"{self.total_tokens['input']:,} in / {self.total_tokens['output']:,} out | "
            f"{len(self.calls)} calls"
        )
