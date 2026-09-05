"""Contract tests for non-destructive response formatting.

The formatter is a presentation transformation. It must never replace a
meaningful authoritative agent response with empty, malformed, or
catastrophically truncated formatter output.
"""

from types import SimpleNamespace

import pytest

from src.agents.config import Config
from src.agents.formatter.node import formatter_node


ORIGINAL = (
    "Your portfolio contains one WAVAX position on Avalanche with negligible "
    "USD value. The wallet currently contains one asset. WAVAX is a medium-risk "
    "asset. Because the wallet is effectively empty, the first recommendation "
    "is to fund it before making allocation decisions. Once funded, consider "
    "diversifying between established assets such as ETH, stablecoins such as "
    "USDC, and a smaller allocation to higher-risk assets."
)


def _install_formatter(monkeypatch, output):
    class Formatter:
        def invoke(self, messages):
            return SimpleNamespace(content=output)

    monkeypatch.setattr(
        Config,
        "get_llm",
        classmethod(
            lambda cls, model=None, temperature=None, with_cost_tracking=True:
                Formatter()
        ),
    )


def _format():
    return formatter_node({
        "final_response": ORIGINAL,
        "nodes_executed": ["portfolio_advisor_node"],
    })["final_response"]


@pytest.mark.parametrize(
    "bad_output",
    [
        "",
        "   \n\t ",
        "##",
        "###",
    ],
)
def test_formatter_rejects_empty_or_malformed_output(monkeypatch, bad_output):
    _install_formatter(monkeypatch, bad_output)

    assert _format() == ORIGINAL


def test_formatter_rejects_catastrophic_truncation(monkeypatch):
    _install_formatter(monkeypatch, "Portfolio overview.")

    assert _format() == ORIGINAL


def test_formatter_exception_falls_back_to_original(monkeypatch):
    class FailingFormatter:
        def invoke(self, messages):
            raise RuntimeError("formatter unavailable")

    monkeypatch.setattr(
        Config,
        "get_llm",
        classmethod(
            lambda cls, model=None, temperature=None, with_cost_tracking=True:
                FailingFormatter()
        ),
    )

    assert _format() == ORIGINAL


def test_formatter_accepts_legitimate_structured_transformation(monkeypatch):
    formatted = (
        "## Portfolio Overview\n\n"
        "Your portfolio contains one **WAVAX** position on Avalanche with "
        "negligible USD value. The wallet currently contains one asset. "
        "WAVAX is a medium-risk asset.\n\n"
        "## Recommendation\n\n"
        "Because the wallet is effectively empty, the first recommendation "
        "is to fund it before making allocation decisions. Once funded, "
        "consider diversifying between established assets such as **ETH**, "
        "stablecoins such as **USDC**, and a smaller allocation to "
        "higher-risk assets."
    )

    _install_formatter(monkeypatch, formatted)

    assert _format() == formatted
