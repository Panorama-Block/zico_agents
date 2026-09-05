import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


class _ImportGraph:
    async def astream_events(self, initial_state, version):
        if False:
            yield None


with (
    patch("src.graphs.nodes.initialize_agents"),
    patch("src.graphs.factory.build_graph", return_value=_ImportGraph()),
):
    sys.modules.pop("src.app", None)
    app_module = importlib.import_module("src.app")


AUTHORITATIVE = (
    "1. Smart-contract risk.\n"
    "2. Stablecoin issuer risk.\n"
    "3. Bridge and interoperability risk.\n"
    "4. Network and liquidity risk.\n"
    "5. Regulatory risk.\n\n"
    "Conclusion: Holding USDC on Avalanche combines issuer, protocol, "
    "network, liquidity, and regulatory risks."
)

PARTIAL_SUFFIX = (
    "2. Stablecoin issuer risk.\n"
    "3. Bridge and interoperability risk.\n"
    "4. Network and liquidity risk.\n"
    "5. Regulatory risk.\n\n"
    "Conclusion: Holding USDC on Avalanche combines issuer, protocol, "
    "network, liquidity, and regulatory risks."
)


def _chain_start(name):
    return {
        "event": "on_chain_start",
        "name": name,
        "data": {},
    }


def _model_chunk(text, *, name="ChatGoogleGenerativeAI", tags=None):
    return {
        "event": "on_chat_model_stream",
        "name": name,
        "tags": tags or [],
        "data": {
            "chunk": SimpleNamespace(content=text),
        },
    }


def _graph_end(response=AUTHORITATIVE):
    return {
        "event": "on_chain_end",
        "name": "LangGraph",
        "data": {
            "output": {
                "final_response": response,
                "response_agent": "default_agent",
                "response_metadata": {},
            }
        },
    }


def _parse_sse(events):
    parsed = []
    for raw in events:
        event_name = None
        data = None
        for line in raw.splitlines():
            if line.startswith("event: "):
                event_name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if event_name:
            parsed.append((event_name, data))
    return parsed


async def _collect(events):
    async def fake_astream_events(initial_state, version):
        assert version == "v2"
        for event in events:
            yield event

    tracker = Mock()
    tracker.get_snapshot.return_value = {}
    tracker.calculate_delta.return_value = {"cost": 0, "calls": 0}

    persisted = AsyncMock()

    with (
        patch.object(app_module.graph, "astream_events", fake_astream_events),
        patch.object(app_module.Config, "get_cost_tracker", return_value=tracker),
        patch.object(app_module, "_persist_response_bg", persisted),
    ):
        generator_factory = app_module._build_event_generator(
            {"messages": []},
            "user-1",
            "conversation-1",
            "fast",
        )
        raw_events = [event async for event in generator_factory()]

    return _parse_sse(raw_events), persisted


@pytest.mark.asyncio
async def test_partial_stream_cannot_override_authoritative_graph_response():
    parsed, persisted = await _collect(
        [
            _chain_start("default_agent_node"),
            _model_chunk(PARTIAL_SUFFIX),
            _graph_end(),
        ]
    )

    done = [data for event, data in parsed if event == "done"]

    assert len(done) == 1
    assert done[0]["response"] == AUTHORITATIVE

    persisted.assert_awaited_once()
    assert persisted.await_args.args[0] == AUTHORITATIVE


@pytest.mark.asyncio
async def test_single_stream_fragment_cannot_override_authoritative_graph_response():
    parsed, persisted = await _collect(
        [
            _chain_start("default_agent_node"),
            _model_chunk("on Avalanche."),
            _graph_end(),
        ]
    )

    done = [data for event, data in parsed if event == "done"]

    assert len(done) == 1
    assert done[0]["response"] == AUTHORITATIVE
    assert persisted.await_args.args[0] == AUTHORITATIVE


@pytest.mark.asyncio
async def test_multiple_internal_model_streams_do_not_define_durable_response():
    parsed, persisted = await _collect(
        [
            _chain_start("default_agent_node"),
            _model_chunk("I should inspect the portfolio."),
            _model_chunk("## Portfolio Overview\nYour portfolio"),
            _graph_end(),
        ]
    )

    done = [data for event, data in parsed if event == "done"]

    assert len(done) == 1
    assert done[0]["response"] == AUTHORITATIVE
    assert persisted.await_args.args[0] == AUTHORITATIVE


@pytest.mark.asyncio
async def test_no_stream_chunks_uses_authoritative_graph_response():
    parsed, persisted = await _collect(
        [
            _chain_start("default_agent_node"),
            _graph_end(),
        ]
    )

    done = [data for event, data in parsed if event == "done"]

    assert len(done) == 1
    assert done[0]["response"] == AUTHORITATIVE
    assert persisted.await_args.args[0] == AUTHORITATIVE


@pytest.mark.asyncio
async def test_done_response_and_persisted_response_are_identical():
    parsed, persisted = await _collect(
        [
            _chain_start("default_agent_node"),
            _model_chunk("partial"),
            _graph_end(),
        ]
    )

    done = [data for event, data in parsed if event == "done"]

    assert len(done) == 1
    persisted_response = persisted.await_args.args[0]

    assert done[0]["response"] == persisted_response
    assert persisted_response == AUTHORITATIVE


@pytest.mark.asyncio
async def test_model_runs_are_correlated_independently_in_boundary_evidence():
    run_one = "model-run-1"
    run_two = "model-run-2"

    def model_chunk(text, run_id, parent_ids):
        return {
            "event": "on_chat_model_stream",
            "name": "ChatGoogleGenerativeAI",
            "run_id": run_id,
            "parent_ids": parent_ids,
            "tags": [],
            "data": {
                "chunk": SimpleNamespace(content=text),
            },
        }

    def model_end(text, run_id, parent_ids, tool_calls=None):
        return {
            "event": "on_chat_model_end",
            "name": "ChatGoogleGenerativeAI",
            "run_id": run_id,
            "parent_ids": parent_ids,
            "tags": [],
            "data": {
                "output": SimpleNamespace(
                    content=text,
                    tool_calls=tool_calls or [],
                ),
            },
        }

    first = "I should inspect available strategy data."
    second = "## Final Answer\nA complete user-facing answer."

    with patch.object(app_module, "update_trace") as update_trace:
        parsed, persisted = await _collect(
            [
                _chain_start("strategy_agent_node"),
                model_chunk(first, run_one, ["root", "strategy"]),
                model_end(
                    first,
                    run_one,
                    ["root", "strategy"],
                    tool_calls=[{"name": "lookup"}],
                ),
                model_chunk(second, run_two, ["root", "strategy"]),
                model_end(
                    second,
                    run_two,
                    ["root", "strategy"],
                ),
                _graph_end(),
            ]
        )

    stream_updates = [
        call.kwargs["value"]
        for call in update_trace.call_args_list
        if call.kwargs.get("section") == "stream"
    ]

    assert len(stream_updates) == 1

    evidence = stream_updates[0]

    assert evidence["model_run_count"] == 2
    assert len(evidence["model_runs"]) == 2

    first_run = evidence["model_runs"][0]
    second_run = evidence["model_runs"][1]

    assert first_run["sequence"] == 1
    assert first_run["name"] == "ChatGoogleGenerativeAI"
    assert first_run["parent_depth"] == 2
    assert first_run["streamed_length"] == len(first)
    assert first_run["end_length"] == len(first)
    assert first_run["streamed_sha256_16"] == first_run["end_sha256_16"]
    assert first_run["tool_call_count"] == 1

    assert second_run["sequence"] == 2
    assert second_run["name"] == "ChatGoogleGenerativeAI"
    assert second_run["parent_depth"] == 2
    assert second_run["streamed_length"] == len(second)
    assert second_run["end_length"] == len(second)
    assert second_run["streamed_sha256_16"] == second_run["end_sha256_16"]
    assert second_run["tool_call_count"] == 0

    assert "model-run-1" not in json.dumps(evidence)
    assert "model-run-2" not in json.dumps(evidence)

    done = [data for event, data in parsed if event == "done"]
    assert len(done) == 1
    assert done[0]["response"] == AUTHORITATIVE
    assert persisted.await_args.args[0] == AUTHORITATIVE
