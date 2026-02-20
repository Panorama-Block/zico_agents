"""
Mode-specific prompt directives for the dual-path system (Fast vs. Reasoning).

Design principle:
  - **Fast mode** adds NO extra instructions.  The agent prompts are already
    optimised for Gemini 2.5 Flash.  Adding constraints degrades output quality.
  - **Reasoning mode** ADDS depth: step-by-step analysis, richer formatting,
    risk warnings, source citation, and structured multi-section responses.

The generic directive is injected by ``entry_node`` into the global system
message.  Per-agent reasoning overrides are injected by each agent node.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Generic directives (injected by entry_node for ALL agents)
# ---------------------------------------------------------------------------

FAST_DIRECTIVE = ""  # Intentionally empty — do not alter agent behaviour.

REASONING_DIRECTIVE = """\

## Response Mode: Deep Reasoning
You are in deep-reasoning mode.  The user expects a thorough, well-structured answer.

- Think step-by-step before answering.  Consider edge cases and nuances.
- Structure longer responses with ## headers and clear sections.
- Use tables when comparing 3+ data points.
- Provide evidence, trade-offs, and risk warnings where relevant.
- Cite sources for factual claims when available.
- Address ambiguities explicitly rather than assuming.
- Prioritize accuracy and depth — the user chose this mode for completeness.\
"""

# ---------------------------------------------------------------------------
# Per-agent overrides — reasoning mode only.
# Fast mode has NO per-agent overrides by design.
# ---------------------------------------------------------------------------

_AGENT_REASONING_OVERRIDES: dict[str, str] = {
    "crypto_agent": """\
## Deep Reasoning — Crypto Data
- Identify ALL assets in the query and decide which metrics matter (price, mcap, FDV, TVL, volume, 24h/7d change).
- Present data in a rich table with all relevant metrics.
- Add 1-2 sentences of context per asset: ranking, proximity to ATH/ATL, sector dominance.
- For comparisons: include a summary row with a relative verdict.\
""",

    "swap_agent": """\
## Deep Reasoning — Swap
Before calling update_swap_intent, reason carefully:
  1. Extract ALL implicit fields from the message in one pass.
  2. If only one network is named, assume both from and to are the same.
  3. Check for potential errors (same-token swap, zero amount, unsupported route).
  4. Note whether this is cross-chain (bridge involved).
When swap_intent_ready: confirm with a full summary.
For balance queries: show the relevant token plus its share of the portfolio.\
""",

    "lending_agent": """\
## Deep Reasoning — Lending
- Recognise action synonyms (supply = deposit, borrow = loan).
- Validate that the asset makes sense for the action on the chosen network.
- When asking for missing fields, add brief context (e.g. which networks have the best rates).
- When lending_intent_ready: for supply, note collateral implications; for borrow, warn about liquidation risk.\
""",

    "staking_agent": """\
## Deep Reasoning — Staking
- Consider whether the user wants Lido specifically or generic staking information.
- Include current APR when available from tools.
- When staking_intent_ready: estimate weekly/monthly earnings and mention stETH liquidity.
- For info requests: structured response — How it works, Current APR, Risks, How to exit.\
""",

    "dca_agent": """\
## Deep Reasoning — DCA
- Analyse the token pair (volatility, liquidity, historical behaviour).
- Evaluate user parameters against guardrails; suggest optimisations if suboptimal.
- Consulting stage: present pair analysis + guardrails + suggested defaults with justification.
- Recommendation stage: parameter table with a "Reason" column.
- Confirmation stage: full summary with projection (total invested, fee estimate).\
""",

    "portfolio_advisor": """\
## Deep Reasoning — Portfolio Analysis
Follow the full analysis structure:
1. **Portfolio Overview** — total value, asset count, chains with holdings.
2. **Complete Holdings Table** — ALL tokens with Risk Level column (emoji indicators).
3. **Allocation Breakdown** — blue chips %, stablecoins %, altcoins %.
4. **Risk Assessment** — per-token analysis, concentration flags, diversification score.
5. **Market Context** — use the search tool for the top 3 holdings.
6. **Recommendations** — specific swap actions with amounts and reasoning.
Assign a numeric health score (e.g. 7.2/10).  Justify every recommendation.\
""",

    "search_agent": """\
## Deep Reasoning — Web Search
- Decompose complex queries into sub-queries when needed.
- Evaluate source credibility; flag conflicts between sources.
- Structure response with ## headers per subtopic.
- Cite sources with links when possible.
- Add a "Caveats" note for uncertain or conflicting information.
- Distinguish confirmed facts from rumours or speculation.\
""",

    "database_agent": """\
## Deep Reasoning — Database Query
- Plan the exploration strategy before making tool calls.
- Identify relevant tables/columns; consider JOINs and aggregations.
- Show the generated SQL in a code block with inline comments.
- Present results in a table plus interpretive analysis.
- If results are empty: explain possible reasons and suggest alternatives.\
""",

    "default_agent": """\
## Deep Reasoning — General
- Assess the user's knowledge level from conversational context.
- For DeFi concepts: explain the "why" beyond the "what"; include practical examples.
- Mention trade-offs and risks where relevant.
- If the query is ambiguous: address the most likely interpretation while noting alternatives.\
""",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_generic_directive(mode: str) -> str:
    """Return the generic directive block for the given mode.

    Returns an empty string for fast mode (no extra instructions needed).
    """
    if mode == "reasoning":
        return REASONING_DIRECTIVE
    return FAST_DIRECTIVE


def get_agent_directive(agent_key: str, mode: str) -> str | None:
    """Return a per-agent override directive, or *None* if none exists.

    Only reasoning mode has per-agent overrides.  Fast mode always returns None.
    """
    if mode != "reasoning":
        return None
    return _AGENT_REASONING_OVERRIDES.get(agent_key)
