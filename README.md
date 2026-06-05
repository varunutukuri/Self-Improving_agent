# AIDEN — Self-Improving Code Agent

A self-improving AI coding agent that generates Python solutions, runs them through pytest, and learns from its own mistakes using semantic memory.

## How It Works

```
Task → Generate code (GPT-4o streaming) → Run pytest
         ↑                                      ↓
     Apply fix                          Tests fail?
         ↑                                      ↓
     Patch (GPT-4o) ← Analyse (GPT-4o-mini) ← Retrieve similar past errors
```

Each failure is embedded with `sentence-transformers` and stored in MySQL. On the next similar error, the agent retrieves the closest past mistake and its fix, passing it as context to the analyser and patcher — making it genuinely self-improving over time.

## Features

- **Live streaming** — generated code appears token-by-token in the Monaco editor
- **Structured critic** — each failed iteration shows an LLM-generated error class, root cause, and fix hint
- **Semantic memory** — cosine similarity search over past failures (threshold-based retrieval)
- **Memory table** — live table of all stored mistakes with similarity bars
- **Light-mode UI** — React + Tailwind, Monaco editor, status bar with token estimates

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, Monaco Editor |
| Backend | FastAPI, Python 3.11, WebSockets |
| LLM | OpenAI GPT-4o (generator/patcher) + GPT-4o-mini (analyser) |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Database | MySQL 8 via `aiomysql` |
| Testing | pytest + pytest-asyncio |
| Infra | Docker Compose |

## Quick Start (Docker)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/self-improving-agent
cd self-improving-agent

# 2. Set secrets
cp backend/.env.example backend/.env
# Edit backend/.env — add your OPENAI_API_KEY and choose DB passwords

# 3. Copy root env (used by docker-compose)
cp backend/.env .env

# 4. Start everything
docker compose up --build

# 5. Open the UI
open http://localhost:5173
```

## Local Dev (no Docker)

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in your values
uvicorn api:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

**Tests**
```bash
cd backend
pytest tests/ -v
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `MYSQL_HOST` | MySQL host (default: `localhost`) |
| `MYSQL_PORT` | MySQL port (default: `3306`, Docker uses `3307`) |
| `MYSQL_USER` | DB user |
| `MYSQL_PASSWORD` | DB password |
| `MYSQL_ROOT_PASSWORD` | MySQL root password (Docker only) |
| `MYSQL_DATABASE` | Database name (default: `agent_db`) |

## Project Structure

```
self-improving-agent/
├── backend/
│   ├── agent/
│   │   ├── agent_context.py   # prompt builders & LLM response parser
│   │   ├── agent_loop.py      # main generate→test→analyse→patch loop
│   │   ├── llm_client.py      # OpenAI async wrapper
│   │   ├── memory_store.py    # semantic memory (cosine similarity)
│   │   └── test_executor.py   # isolated pytest subprocess runner
│   ├── db/
│   │   ├── connection.py      # aiomysql connection pool
│   │   └── schema.sql         # table definitions
│   ├── tests/                 # pytest test suite (21 tests)
│   ├── api.py                 # FastAPI app (HTTP + WebSocket)
│   └── requirements.txt
└── frontend/
    └── src/
        ├── components/
        │   ├── LeftPanel.jsx      # task input + live code editor
        │   ├── TaskInput.jsx      # prompt textarea + controls
        │   ├── IterationCard.jsx  # per-iteration result card
        │   ├── MemoryTable.jsx    # bottom memory log table
        │   ├── StatusBar.jsx      # status line
        │   └── CodePanel.jsx      # Monaco editor wrapper
        └── hooks/
            └── useAgentSocket.js  # WebSocket state management
```

## License

MIT
