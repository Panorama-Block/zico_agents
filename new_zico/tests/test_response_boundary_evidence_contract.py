from __future__ import annotations

from src.diagnostics.response_boundary import (
    clear_traces_for_tests,
    get_latest_trace_for_user,
    start_trace,
    update_trace,
)


def setup_function():
    clear_traces_for_tests()


def test_trace_is_scoped_to_authenticated_user():
    start_trace("0xAAAA", "conversation-a")
    update_trace(
        "0xAAAA",
        "conversation-a",
        section="stream",
        value={"streamed_length": 900},
    )

    assert get_latest_trace_for_user("0xaaaa")["conversation_id"] == "conversation-a"
    assert get_latest_trace_for_user("0xbbbb") is None


def test_latest_trace_wins_for_same_user():
    start_trace("0xaaaa", "conversation-a")
    start_trace("0xaaaa", "conversation-b")

    trace = get_latest_trace_for_user("0xaaaa")

    assert trace["conversation_id"] == "conversation-b"


def test_trace_contains_only_supplied_diagnostic_metadata():
    start_trace("0xaaaa", "conversation-a")
    update_trace(
        "0xaaaa",
        "conversation-a",
        section="extracted",
        value={
            "selected_index": 4,
            "agent": "default_agent",
            "length": 42,
            "sha256_16": "0123456789abcdef",
        },
    )

    trace = get_latest_trace_for_user("0xaaaa")

    assert trace["extracted"]["length"] == 42
    assert "response" not in repr(trace).lower()
    assert "prompt" not in repr(trace).lower()


def test_formatter_records_request_scoped_boundary():
    from src.agents.formatter.node import formatter_node

    original = "Short response used to verify request-scoped formatter diagnostics."

    start_trace("0xaaaa", "conversation-format")

    result = formatter_node({
        "final_response": original,
        "user_id": "0xaaaa",
        "conversation_id": "conversation-format",
        "nodes_executed": ["default_agent_node"],
    })

    trace = get_latest_trace_for_user("0xaaaa")

    assert result["final_response"] == original
    assert trace["formatter"] is not None

    assert trace["formatter"]["input"]["length"] == len(original)
    assert trace["formatter"]["input"]["sha256_16"]

    assert trace["formatter"]["output"]["length"] == len(original)
    assert trace["formatter"]["output"]["sha256_16"]
    assert trace["formatter"]["output"]["passthrough"] is True

    assert original not in repr(trace)
