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

### Memory write policy

Two thresholds do two different jobs:

| Threshold | Purpose |
|---|---|
| cosine ≥ 0.60 | **Retrieval** — top-3 similar past errors injected into analyser/patcher prompts |
| cosine ≥ 0.85 | **Deduplication** — treat as the same mistake; append a fix attempt instead of inserting a new row |

Every failure is written with `result="failed"`. When a later iteration **passes**, the preceding failure is written again with `result="passed"` — which dedups onto the same row and increments its `success_count`. That's what makes the store a record of fixes that *worked*, rather than only of approaches that didn't.

## Features

- **Live streaming** — generated code appears token-by-token in the Monaco editor
- **Structured critic** — the analyser returns strict JSON (`error_class`, `root_cause`, `fix_hint`) with a deterministic regex fallback if parsing fails
- **Two-phase iteration cards** — test results render immediately via `iteration_failed`; LLM critique arrives separately via `iteration_analysis` and patches the same card, so the UI never blocks on the analyser call
- **Semantic memory** — cosine similarity search with separate retrieval and dedup thresholds
- **Per-test granularity** — pytest `-v` output is parsed into individual pass/fail pills
- **Memory table** — live table of all stored mistakes with similarity bars
- **Light-mode UI** — React + Tailwind, Monaco editor, status bar with token estimates

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, Monaco Editor |
| Backend | FastAPI, Python 3.11, WebSockets |
| LLM | OpenAI GPT-4o (generator/patcher) + GPT-4o-mini (analyser) |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Database | MySQL 9.0 via `aiomysql` |
| Testing | pytest + pytest-asyncio (25 tests, 91% coverage) |
| Lint/CI | ruff + GitHub Actions, coverage gate at 85% |
| Infra | Docker Compose |

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/memories` | 50 most recent memory entries with their latest fix attempt |
| `WS` | `/ws/run` | Send `{"task": "...", "max_iterations": 5}`; receive the event stream below |

### WebSocket events

| Event | Payload |
|---|---|
| `token` | One streamed LLM token for the live editor |
| `status` | Phase message (`Generating code...`, `Running tests...`, `Analyzing error...`) |
| `iteration_failed` | Code, test output, per-test cases, error type, similarity score, memory hit flag |
| `iteration_analysis` | `error_class`, `root_cause`, `fix_hint` — patches the matching card |
| `memory_saved` | Emitted after a memory row is committed; the UI refetches `/memories` on this rather than on `iteration_failed`, which would query before the write lands |
| `complete` | Final passing code, tests, per-test cases, total iterations |
| `max_iterations_reached` | Last code and error after exhausting retries |
| `error` | Server-side failure message |

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
pytest tests/ -v --cov=agent --cov=db     # 25 tests, 91% coverage, ~3s
ruff check .                              # lint
```

The suite stubs `openai` at import time (see `tests/conftest.py`) and mocks the
aiomysql pool, so it runs with no API key, no database, and zero API cost.

## Security note

`test_executor.py` runs LLM-generated code via `subprocess` in a temporary
directory with a 30-second timeout. That bounds runtime and guarantees cleanup,
but it is **not a sandbox** — there is no container, network isolation, or
resource limit, so generated code can read the filesystem and make network
calls. Fine for local single-user use; add Docker with `--network=none`,
a read-only root filesystem, and memory limits before exposing it to anyone else.

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
│   ├── tests/                 # pytest test suite (25 tests)
│   ├── api.py                 # FastAPI app (HTTP + WebSocket)
│   ├── ruff.toml              # pinned lint rule set
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── LeftPanel.jsx      # task input + live code editor
│       │   ├── TaskInput.jsx      # prompt textarea + controls
│       │   ├── IterationFeed.jsx  # iteration card list
│       │   ├── IterationCard.jsx  # per-iteration result card
│       │   ├── MemoryTable.jsx    # bottom memory log table
│       │   ├── StatusBar.jsx      # status line
│       │   └── CodePanel.jsx      # Monaco editor wrapper
│       └── hooks/
│           └── useAgentSocket.js  # WebSocket state management
└── .github/workflows/ci.yml   # ruff + pytest w/ coverage gate, frontend build
```

## Known limitations

- **Execution is not sandboxed** — see the security note above.
- **Memory search is a full table scan.** `get_relevant_memories` loads every row and computes cosine similarity in numpy. Fine below ~10k rows; needs pgvector/Qdrant or MySQL 9's native `VECTOR` type beyond that.
- **The agent writes its own tests.** Passing means the code satisfies tests the same model generated, so it validates internal consistency rather than correctness against intent. A held-out test set per task would fix this.
- **The `runs` table is defined but never written to.** Run history is not yet persisted; only memory rows are.
- **No load testing.** The architecture is session-isolated, but no concurrency claim has been measured.

## License

MIT
