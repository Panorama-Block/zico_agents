"""
Integration tests for the Supervisor Agent.
"""
import pytest
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.supervisor.agent import Supervisor, ChatMessage
from src.agents.config import Config

@pytest.fixture
def supervisor():
    """Create a Supervisor instance for testing."""
    llm = ChatGoogleGenerativeAI(
        model=Config.GEMINI_MODEL,
        temperature=0.7,
        google_api_key=Config.GEMINI_API_KEY
    )
    return Supervisor(llm)

def test_eth_price_query(supervisor):
    """Test that the supervisor can handle an ETH price query."""
    # Create test messages
    messages: list[ChatMessage] = [
        {
            "role": "user",
            "content": "What is the current price of ETH?"
        }
    ]

    # Get response from supervisor
    result = supervisor.invoke(messages)

    # Validate structure
    assert isinstance(result, dict)
    assert "messages" in result
    assert "agent" in result
    assert "response" in result

    # Validate that the correct agent was used
    assert result["agent"] != "supervisor", "Supervisor responded instead of an agent."
    assert "crypto" in result["agent"], "Expected a crypto-related agent to handle the query."

    # Validate the content
    content = result["response"].lower()
    print(f"DEBUG: Final agent response: {content}")

    assert any(keyword in content for keyword in ["eth", "ethereum", "price"]), f"Expected keywords not found in: {content}"
    assert any(char.isdigit() for char in content), "Expected numerical value in response (price)."
