import pytest
import time
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from src.agents.crypto_data.agent import CryptoDataAgent
from src.agents.config import Config

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
async def test_response_time(crypto_agent):
    """Test that the agent responds within a reasonable time."""
    query = "What is the current price of Bitcoin?"
    agent = crypto_agent.agent
    
    start_time = time.time()
    response = await agent.ainvoke(
        {"messages": [HumanMessage(content=query)]}
    )
    end_time = time.time()
    
    duration = end_time - start_time
    print(f"\nResponse time: {duration:.2f} seconds")
    
    assert response is not None
    assert duration < 10.0, f"Response took too long: {duration:.2f} seconds"
