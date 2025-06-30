# Zico Multi-Agent System

A sophisticated multi-agent system built with LangGraph, FastAPI, and Google's Gemini AI for intelligent conversation routing and specialized task handling.

## 🚀 Features

- **Multi-Agent Architecture**: Intelligent routing between specialized agents
- **LangGraph Integration**: Stateful conversation flows with proper state management
- **Real-time Crypto Data**: Live cryptocurrency price and market data
- **Conversation Management**: Persistent conversation state and history
- **Performance Monitoring**: Agent performance metrics and analytics
- **RESTful API**: Clean FastAPI endpoints for easy integration
- **Extensible Design**: Easy to add new agents and capabilities

## 🏗️ Architecture

### Core Components

1. **Supervisor Agent**: Routes messages to appropriate specialized agents
2. **Crypto Data Agent**: Handles cryptocurrency-related queries
3. **General Agent**: Manages general conversation and queries
4. **Conversation Manager**: Manages conversation state and persistence
5. **Agent Registry**: Central registry for all agents in the system

### LangGraph Flow

```
User Message → Supervisor → Route Decision → Specialized Agent → Response
     ↓              ↓              ↓              ↓              ↓
Conversation → Context → State → Processing → Agent Response
```

## 📦 Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd new_zico
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

5. **Run the application**
```bash
python -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

## 🔧 Configuration

### Environment Variables

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-pro
GEMINI_EMBEDDING_MODEL=models/embedding-001
```

### Agent Configuration

Agents can be configured in `src/agents/config.py`:

```python
AGENTS_CONFIG = {
    "agents": [
        {
            "name": "crypto_data",
            "description": "Handles cryptocurrency-related queries",
            "type": "specialized",
            "enabled": True,
            "priority": 1
        },
        {
            "name": "general",
            "description": "Handles general conversation and queries",
            "type": "general",
            "enabled": True,
            "priority": 2
        }
    ]
}
```

## 📡 API Usage

### Chat Endpoint

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the price of Bitcoin?",
    "user_id": "user123",
    "conversation_id": "conv456"
  }'
```

**Response:**
```json
{
  "response": "The current price of Bitcoin is $43,250.50",
  "agent_name": "crypto_agent",
  "agent_type": "crypto_data",
  "conversation_id": "conv456",
  "message_id": "msg789",
  "metadata": {
    "price_source": "CoinGecko",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "next_agent": null,
  "requires_followup": false,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Conversation Management

```bash
# Get all conversations for a user
GET /conversations/{user_id}

# Get messages from a specific conversation
GET /conversations/{user_id}/{conversation_id}/messages

# Delete a conversation
DELETE /conversations/{user_id}/{conversation_id}

# Reset a conversation (clear messages)
POST /conversations/{user_id}/reset
```

## 🤖 Adding New Agents

### 1. Create Agent Class

```python
# src/agents/my_agent/agent.py
from src.agents.base_agent import BaseAgent
from src.models.chatMessage import AgentType, AgentResponse

class MyAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(
            name="my_agent",
            agent_type=AgentType.SPECIALIZED,
            llm=llm,
            description="Handles specific tasks"
        )
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> AgentResponse:
        # Your agent logic here
        response_content = "Processed by MyAgent"
        return self.create_agent_response(response_content)
    
    def get_capabilities(self) -> List[str]:
        return ["task1", "task2", "task3"]
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        # Define when this agent should handle messages
        return "my_keyword" in message.lower()
    
    def get_confidence_score(self, message: str, context: Dict[str, Any] = None) -> float:
        # Return confidence score (0.0 to 1.0)
        if "my_keyword" in message.lower():
            return 0.9
        return 0.1
```

### 2. Register Agent

```python
# In your supervisor or main application
from src.agents.my_agent.agent import MyAgent
from src.agents.base_agent import agent_registry

my_agent = MyAgent(llm)
agent_registry.register_agent(my_agent)
```

### 3. Update Supervisor Routing

Add routing logic in the supervisor's `_route_to_agent` method:

```python
def _route_to_agent(self, state: ConversationState) -> str:
    # ... existing logic ...
    
    # Add your agent routing
    if "my_keyword" in content:
        return "my_agent"
    
    # ... rest of logic ...
```

## 📊 Monitoring and Analytics

### Agent Performance

```bash
# Get performance metrics for all agents
GET /agents/performance

# Get specific agent info
GET /agents/{agent_name}/info
```

### Conversation Analytics

```bash
# Get conversation statistics
GET /conversations/{user_id}/stats

# Export conversation data
GET /conversations/{user_id}/{conversation_id}/export
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_supervisor.py
```

## 🚀 Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Setup

For production, consider:

1. **Database**: Use PostgreSQL or MongoDB for conversation persistence
2. **Caching**: Redis for session management and caching
3. **Monitoring**: Prometheus + Grafana for metrics
4. **Logging**: Structured logging with ELK stack
5. **Security**: API keys, rate limiting, CORS configuration

## 🔍 Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### LangGraph Visualization

```python
# Visualize the conversation flow
from langgraph.graph import StateGraph
graph = supervisor.supervisor_graph
graph.get_graph().draw_mermaid()
```

## 📈 Performance Optimization

1. **Agent Caching**: Cache agent responses for similar queries
2. **Context Window**: Limit context messages to prevent token overflow
3. **Async Processing**: Use background tasks for non-critical operations
4. **Connection Pooling**: Reuse LLM connections
5. **Response Streaming**: Stream responses for long-running operations

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

- Create an issue in the repository
- Check the documentation
- Review the test examples

## 🔮 Roadmap

- [ ] Add more specialized agents (research, analysis, etc.)
- [ ] Implement agent learning and adaptation
- [ ] Add support for file uploads and document processing
- [ ] Implement real-time collaboration features
- [ ] Add advanced analytics and reporting
- [ ] Support for multiple LLM providers
- [ ] Mobile app integration 