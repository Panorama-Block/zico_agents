# Zico Multi-Agent System

Zico is a multi-agent application that helps users execute token swaps and access crypto insights through a single conversational interface. A LangGraph-powered supervisor coordinates specialized agents—swap, market data, search, and database—to assemble the best answer for each request.

## 🚀 Core Responsibilities

- **Conversation routing:** The supervisor (`src/agents/supervisor/agent.py`) evaluates every turn and selects either a direct reply or delegation to a specialized agent.
- **Specialized tooling:** Bundled agents include:
  - `crypto_agent` (market data via CoinGecko integrations)
  - `swap_agent` (stateful token swap collection backed by `SwapStateRepository`)
  - `search_agent` (Tavily-backed retrieval, enabled when `TAVILY_API_KEY` is present)
  - `database_agent` (ClickHouse assistant, registered only when the database is reachable)
  - `default_agent` (general-purpose fallback)
- **State management:** `ChatManager` (`src/service/chat_manager.py`) stores complete histories keyed by `user_id` and `conversation_id`, ensuring downstream agents receive prior context.
- **Swap persistence:** `src/agents/swap/storage.py` persists intents, metadata, and history to a JSON-backed repository so multi-turn flows survive multiple requests.
- **API surface:** `src/app.py` exposes `/chat`, agent discovery routes, and conversation utilities for frontend or automation clients.

## 🏗️ Runtime Architecture

```
User → FastAPI /chat → ChatManager → Supervisor (Gemini 2.5 Flash)
       ↑                              ↓
   history persistence      Specialized agent (crypto / swap / search / DB / default)
       ↑                              ↓
 metadata snapshot / swap state  ←    Response payload
```

- **FastAPI (`src/app.py`):** Validates inbound payloads, appends them to the chat store, invokes the supervisor, records the reply, and returns a trimmed response.
- **Supervisor:** Built with LangGraph `create_supervisor`; handles routing heuristics, fallback chains, and swap-session scoping.
- **Agent toolchains:** Each agent wraps LangChain tools (CoinGecko, Tavily, ClickHouse, swap state helpers) and is instantiated once per application lifecycle.
- **Metadata layer (`src/agents/metadata.py`):** Surfaces swap status and crypto tool output so API responses can include structured context.

## 📦 Getting Started

1. **Clone the repository**
   ```bash
   git clone <repository-url>
    cd new_zico
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**  
   Create `.env` (copy `.env.example` if available) and set at minimum:
   ```env
   GEMINI_API_KEY=your_google_ai_studio_key
   ```

   Optional variables:
   - `TAVILY_API_KEY` – enables the search agent.
   - `GLACIER_API_KEY` – required if the ClickHouse database agent relies on Glacier-provided credentials.
   - `SWAP_STATE_PATH` – custom path for swap intent persistence (defaults to `src/agents/swap/swap_state.json`).

5. **Run the API**
   ```bash
   uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
   ```

## 🔧 Runtime Notes

- Gemini model selection is fixed in `src/agents/config.py` (`gemini-2.5-flash` with `models/embedding-001` for embeddings). Override the constant if a different model is required.
- The supervisor only instantiates the database agent when `src/agents/database/client.is_database_available()` returns `True`.
- Agents are singletons created at startup; restart the service when changing prompts or tools.
- Conversation state is currently in memory—persist it externally if you need durability across restarts.

## 📡 API Overview

### `POST /chat`

Send a user message and receive the supervisor’s reply.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
        "message": {
          "role": "user",
          "content": "Swap 10 AVAX to USDC on Ethereum.",
          "metadata": {}
        },
        "user_id": "alice",
        "conversation_id": "session-1",
        "wallet_address": "alice-wallet",
        "chain_id": "default"
      }'
```

**Response**
```json
{
  "response": "Sure — which network will you be swapping from?",
  "agentName": "token swap",
  "metadata": {
    "status": "collecting",
    "missing_fields": ["from_network", "to_network", "amount"],
    "pending_question": "From which network?"
  }
}
```

Key details:
- `agentName` matches the human-readable labels defined in `src/app.py`.
- Swap replies include metadata from `metadata.get_swap_agent` so the frontend can show workflow progress.

### Additional endpoints

- `GET /agents/available` – returns all known agents and the subset currently exposed to the UI.
- `POST /agents/selected` – update the preferred agent shortlist.
- `GET /chat/messages` – fetch the full transcript for a `conversation_id`/`user_id` pair (query parameters).
- `GET /chat/conversations` – list conversation identifiers tracked for a user.

## 🔍 Search & Database Agents

- **Search agent:** Wraps LangGraph’s ReAct helper with Tavily tools (`src/agents/search/tools.py`). Without `TAVILY_API_KEY`, the agent logs a warning and the supervisor falls back to default answers when necessary.
- **Database agent:** Runnable that binds ClickHouse tooling (`src/agents/database/tools.py`). Ensure the configured ClickHouse endpoint is reachable before relying on it in production.

## 🧪 Testing

```bash
pytest                   # run all tests
pytest tests/unit/...    # target specific suites
```

Swap storage/tools have dedicated unit tests. Add new tests alongside existing modules when extending behaviour.

## 🤖 Extending the System

1. **Create a new agent** under `src/agents/<name>/`, following the patterns from `crypto_data`, `swap`, or `search`.
2. **Publish tools** via LangChain Tool definitions so the ReAct loop can interact with external services.
3. **Register the agent** inside the supervisor constructor (`src/agents/supervisor/agent.py`) and update the prompt description.
4. **Expose metadata** through FastAPI if the frontend or downstream systems need it.
5. **Add tests** to cover both successful flows and failure handling.

Encode the desired response policy (the current stack expects English output) in any new system prompt to stay consistent.

## 🧭 Operational Checklist

- Logging is configured in `src/app.py` to stream to stdout; adjust levels/handlers as needed.
- Monitor the swap-state JSON file if you run many concurrent conversations—migrate to a persistent datastore for production workloads.
- Secure the API before exposing it publicly (authentication, HTTPS, rate limiting).

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
