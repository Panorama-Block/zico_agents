"""
Integration tests for the Crypto Data Agent.
"""
import pytest
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.crypto_data.agent import CryptoDataAgent
from src.agents.config import Config

import os

@pytest.fixture
def crypto_agent():
    """Create a CryptoDataAgent instance for testing."""
    llm = ChatGoogleGenerativeAI(
        model=Config.DEFAULT_MODEL,
        temperature=0.7,
        google_api_key=os.getenv("GEMINI_API_KEY")
    )
    return CryptoDataAgent(llm)

@pytest.mark.asyncio
async def test_eth_price_query(crypto_agent):
    """Test that the agent can fetch ETH price."""
    # Create a test query
    query = "What is the current price of ETH?"

    agent = crypto_agent.agent
    
    # Get response from agent
    response = await agent.ainvoke(
        {"messages": [HumanMessage(content=query)]}
    )
    
    # Debug: Print the actual response
    print(f"DEBUG: Crypto agent response: {response}")
    
    # Basic assertions
    assert response is not None
    assert isinstance(response, dict)
    assert "messages" in response
    
    # Check if the response contains price information
    messages = response["messages"]
    assert len(messages) > 0
    
    # Get the last message (assistant's response)
    last_message = messages[-1]
    assert last_message.type == "ai"  # Check if it's an AI message
    
    # Check if the response contains price information
    content = last_message.content
    if isinstance(content, list):
        content = " ".join(str(item) for item in content)
    content = content.lower()
    print(f"DEBUG: Crypto agent content: {content}")
    assert any(keyword in content for keyword in ["eth", "ethereum", "price"]), f"Expected keywords not found in: {content}"
    assert any(char.isdigit() for char in content)  # Should contain numbers for price 