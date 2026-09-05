from langchain_core.messages import AIMessage

from src.graphs.utils import (
    extract_response_from_graph,
    get_text_content,
)


FIRST = "Holding USDC on the Avalanche network"

REST = (
    " involves several risks. "
    "1. Smart contract risk. "
    "2. Stablecoin issuer risk. "
    "3. Bridge risk. "
    "4. Network and liquidity risk. "
    "5. Regulatory risk."
)

FULL = FIRST + REST
CANONICAL = FIRST + "\n\n" + REST.strip()


def _mixed_message():
    return AIMessage(
        content=[
            {
                "type": "text",
                "text": FIRST,
            },
            REST,
        ],
        name="strategy_agent",
    )


def test_get_text_content_preserves_mixed_dict_and_string_parts():
    message = _mixed_message()

    actual = get_text_content(message)

    assert actual is not None
    assert actual == CANONICAL
    assert FIRST in actual
    assert REST.strip() in actual


def test_extract_response_from_graph_preserves_complete_multipart_answer():
    message = _mixed_message()

    agent, response, messages = extract_response_from_graph(
        {
            "messages": [message],
        }
    )

    assert agent == "strategy_agent"
    assert response == CANONICAL
    assert FIRST in response
    assert REST.strip() in response
    assert messages == [message]


def test_langchain_native_text_contains_every_multipart_text_segment():
    message = _mixed_message()

    assert message.text == FULL
