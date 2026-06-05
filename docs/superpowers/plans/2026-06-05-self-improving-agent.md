# Self-Improving Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-improving AI coding agent that generates Python code, runs tests in a sandbox, diagnoses failures semantically, and iterates until tests pass — with persistent mistake memory across sessions.

**Architecture:** A FastAPI backend orchestrates three LLM roles (generator → analyzer → patcher) in a loop, streaming events over WebSocket to a React frontend. Semantic mistake memory uses sentence-transformers embeddings stored as JSON in MySQL, with cosine similarity computed in Python. Each WebSocket connection is a fully isolated session with its own AgentContext instance.

**Tech Stack:** Python 3.11, FastAPI, aiomysql, MySQL 9.0, sentence-transformers (all-MiniLM-L6-v2), scikit-learn, OpenAI GPT-4o/GPT-4o-mini, React 18, Vite, Tailwind CSS, @monaco-editor/react, Docker Compose.

---

## File Map

### Created from scratch

**Root**
- `docker-compose.yml` — MySQL 9.0 + backend + frontend orchestration
- `.gitignore` — excludes `.env`, `node_modules`, `__pycache__`, `.venv`
- `README.md` — setup and run instructions

**Backend**
- `backend/requirements.txt`
- `backend/.env.example`
- `backend/Dockerfile`
- `backend/db/__init__.py`
- `backend/db/schema.sql` — DDL for memories, fix_attempts, runs tables
- `backend/db/connection.py` — aiomysql pool singleton
- `backend/agent/__init__.py`
- `backend/agent/llm_client.py` — AsyncOpenAI wrapper, standard + streaming
- `backend/agent/test_executor.py` — subprocess pytest runner in tempdir
- `backend/agent/agent_context.py` — AgentContext dataclass + prompt builders
- `backend/agent/memory_store.py` — embedding lookup + MySQL persistence
- `backend/agent/agent_loop.py` — full agent orchestration, yields events
- `backend/api.py` — FastAPI lifespan, CORS, /health, /ws/run

**Tests**
- `backend/tests/__init__.py`
- `backend/tests/test_test_executor.py` — unit tests for subprocess runner
- `backend/tests/test_agent_context.py` — unit tests for prompt builders and parse
- `backend/tests/test_memory_store.py` — unit tests with mock DB pool

**Frontend**
- `frontend/Dockerfile`
- `frontend/index.html`
- `frontend/package.json`
- `frontend/vite.config.js`
- `frontend/tailwind.config.js`
- `frontend/src/main.jsx`
- `frontend/src/App.jsx`
- `frontend/src/hooks/useAgentSocket.js`
- `frontend/src/components/TaskInput.jsx`
- `frontend/src/components/IterationFeed.jsx`
- `frontend/src/components/IterationCard.jsx`
- `frontend/src/components/CodePanel.jsx`
- `frontend/src/components/MemoryLog.jsx`

---

## Task 1: Project Scaffold

**Files:**
- Create: `docker-compose.yml`
- Create: `.gitignore`
- Create: `README.md`
- Create: all `__init__.py` files
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`

- [ ] **Step 1: Create the folder structure**

```bash
mkdir -p backend/agent backend/db backend/tests
mkdir -p frontend/src/components frontend/src/hooks
mkdir -p architecture docs/superpowers/plans
touch backend/agent/__init__.py backend/db/__init__.py backend/tests/__init__.py
```

- [ ] **Step 2: Create `.gitignore`**

```
.env
node_modules/
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.DS_Store
```

- [ ] **Step 3: Create `backend/requirements.txt`**

```
openai
fastapi
uvicorn[standard]
aiomysql
sentence-transformers
scikit-learn
numpy
python-dotenv
pytest
pytest-asyncio
```

- [ ] **Step 4: Create `backend/.env.example`**

```
OPENAI_API_KEY=sk-...
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=agent_user
MYSQL_PASSWORD=yourpassword
MYSQL_ROOT_PASSWORD=rootpassword
MYSQL_DATABASE=agent_db
```

- [ ] **Step 5: Create `docker-compose.yml`**

```yaml
version: "3.9"
services:
  db:
    image: mysql:9.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: agent_db
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./backend/db/schema.sql:/docker-entrypoint-initdb.d/schema.sql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: ./backend/.env
    depends_on:
      db:
        condition: service_healthy
    command: uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4

  frontend:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - backend

volumes:
  mysql_data:
```

- [ ] **Step 6: Create `README.md`**

```markdown
# Self-Improving Agent

## Quick Start

1. Copy env file: `cp backend/.env.example backend/.env` — fill in your values
2. Start services: `docker compose up --build`
3. Open: `http://localhost:5173`

## Local Dev (no Docker)

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

## Run Tests

```bash
cd backend
pytest tests/ -v
```
```

- [ ] **Step 7: Commit**

```bash
git init
git add .gitignore README.md docker-compose.yml backend/requirements.txt backend/.env.example backend/agent/__init__.py backend/db/__init__.py backend/tests/__init__.py
git commit -m "chore: project scaffold and folder structure"
```

---

## Task 2: Database Schema and Connection Pool

**Files:**
- Create: `backend/db/schema.sql`
- Create: `backend/db/connection.py`

- [ ] **Step 1: Create `backend/db/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS memories (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    error_text    TEXT NOT NULL,
    embedding     JSON NOT NULL,
    success_count INT DEFAULT 0,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fix_attempts (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    memory_id  INT NOT NULL,
    fix_text   TEXT NOT NULL,
    result     VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS runs (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    task       TEXT NOT NULL,
    iterations JSON,
    status     VARCHAR(20) DEFAULT 'running',
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_session (session_id)
);
```

- [ ] **Step 2: Create `backend/db/connection.py`**

```python
import aiomysql
import os

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            db=os.getenv("MYSQL_DATABASE", "agent_db"),
            minsize=5,
            maxsize=20,
            autocommit=True,
        )
    return _pool

async def close_pool():
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
```

- [ ] **Step 3: Verify MySQL starts via Docker**

```bash
docker compose up db -d
docker compose ps
# should show db healthy
```

- [ ] **Step 4: Commit**

```bash
git add backend/db/schema.sql backend/db/connection.py
git commit -m "feat: database schema and aiomysql connection pool"
```

---

## Task 3: LLM Client

**Files:**
- Create: `backend/agent/llm_client.py`

- [ ] **Step 1: Create `backend/.env` from example and add your key**

```bash
cp backend/.env.example backend/.env
# edit backend/.env — add real OPENAI_API_KEY
```

- [ ] **Step 2: Create `backend/agent/llm_client.py`**

```python
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def call_llm(system_prompt: str, user_prompt: str,
                   temperature: float = 0.2, model: str = "gpt-4o") -> str:
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content

async def call_llm_stream(system_prompt: str, user_prompt: str, temperature: float = 0.2):
    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=temperature,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
```

- [ ] **Step 3: Smoke test the client (manual, run from backend/ dir)**

```bash
cd backend
python -c "
import asyncio
from agent.llm_client import call_llm
async def t():
    r = await call_llm('You are helpful.', 'Say OK in one word.')
    print(r)
asyncio.run(t())
"
# Expected: 'OK' or similar one-word response
```

- [ ] **Step 4: Commit**

```bash
git add backend/agent/llm_client.py backend/.env.example
git commit -m "feat: OpenAI async LLM client with streaming support"
```

---

## Task 4: Test Executor

**Files:**
- Create: `backend/agent/test_executor.py`
- Create: `backend/tests/test_test_executor.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_test_executor.py`:

```python
from agent.test_executor import run_tests, _extract_error_type, _extract_error_summary

def test_passing_code():
    code = "def add(a, b):\n    return a + b\n"
    tests = "def test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result.passed is True
    assert "1 passed" in result.output

def test_failing_code():
    code = "def add(a, b):\n    return a - b\n"
    tests = "def test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result.passed is False
    assert result.error_type == "AssertionError"

def test_syntax_error():
    code = "def add(a, b)\n    return a + b\n"
    tests = "def test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result.passed is False

def test_extract_error_type_assertion():
    output = "FAILED test_solution.py::test_add - AssertionError: assert 0 == 3"
    assert _extract_error_type(output) == "AssertionError"

def test_extract_error_type_unknown():
    assert _extract_error_type("some random output") == "UnknownError"

def test_extract_error_summary_non_empty():
    output = "short line\n===\nTest failed\n"
    summary = _extract_error_summary(output)
    assert len(summary) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_test_executor.py -v
# Expected: ImportError or similar — module not yet created
```

- [ ] **Step 3: Create `backend/agent/test_executor.py`**

```python
import subprocess
import tempfile
import os
import re
from dataclasses import dataclass

@dataclass
class TestResult:
    passed: bool
    output: str
    error_type: str
    error_summary: str

def run_tests(code: str, tests: str) -> TestResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        code_path  = os.path.join(tmpdir, "solution.py")
        tests_path = os.path.join(tmpdir, "test_solution.py")

        with open(code_path,  "w") as f: f.write(code)
        with open(tests_path, "w") as f:
            f.write("from solution import *\n\n")
            f.write(tests)

        result = subprocess.run(
            ["python", "-m", "pytest", tests_path, "-v", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmpdir,
        )

    output = result.stdout + result.stderr
    passed = result.returncode == 0
    return TestResult(
        passed=passed,
        output=output,
        error_type=_extract_error_type(output),
        error_summary=_extract_error_summary(output),
    )

def _extract_error_type(output: str) -> str:
    match = re.search(r'(AssertionError|IndexError|TypeError|ValueError|'
                      r'KeyError|AttributeError|SyntaxError|NameError|'
                      r'ZeroDivisionError|RecursionError)', output)
    return match.group(1) if match else "UnknownError"

def _extract_error_summary(output: str) -> str:
    lines = output.strip().split("\n")
    for line in reversed(lines):
        if line.strip() and not line.startswith("=") and not line.startswith("-"):
            return line.strip()[:200]
    return "Test failed"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_test_executor.py -v
# Expected: 6 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/agent/test_executor.py backend/tests/test_test_executor.py
git commit -m "feat: sandboxed pytest executor with error type extraction"
```

---

## Task 5: Agent Context

**Files:**
- Create: `backend/agent/agent_context.py`
- Create: `backend/tests/test_agent_context.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_agent_context.py`:

```python
from agent.agent_context import AgentContext, IterationSummary

def test_build_generator_prompt_first_iteration():
    ctx = AgentContext(task="Write a sort function", session_id="abc")
    system, user = ctx.build_generator_prompt()
    assert "## CODE" in system
    assert "## TESTS" in system
    assert "Write a sort function" in user
    assert "Previous attempt" not in user

def test_build_generator_prompt_with_history():
    ctx = AgentContext(task="Write a sort function", session_id="abc")
    ctx.update_history("AssertionError", "fixed indexing", "failed")
    _, user = ctx.build_generator_prompt()
    assert "Previous attempt failed" in user
    assert "AssertionError" in user

def test_build_analyzer_prompt_no_memories():
    ctx = AgentContext(task="Sort task", session_id="abc")
    ctx.current_code = "def sort(x): return x"
    ctx.current_error = "AssertionError: assert [3,1] == [1,3]"
    system, user = ctx.build_analyzer_prompt([])
    assert "root cause" in system.lower()
    assert "Sort task" in user
    assert "AssertionError" in user

def test_build_analyzer_prompt_with_memories():
    ctx = AgentContext(task="Sort task", session_id="abc")
    ctx.current_code = "def sort(x): return x"
    ctx.current_error = "error"
    memories = [{"error_text": "off by one", "fix_attempts": [{"fix_text": "use <="}]}]
    _, user = ctx.build_analyzer_prompt(memories)
    assert "off by one" in user
    assert "use <=" in user

def test_build_patcher_prompt_includes_history_and_memories():
    ctx = AgentContext(task="Sort task", session_id="abc")
    ctx.current_code = "def sort(x): return x"
    ctx.current_analysis = "Returns input unchanged"
    ctx.update_history("AssertionError", "tried reversing", "failed")
    memories = [{"error_text": "wrong sort", "fix_attempts": [{"fix_text": "use sorted()"}]}]
    system, user = ctx.build_patcher_prompt(memories)
    assert "## CODE" in system
    assert "tried reversing" in user
    assert "use sorted()" in user

def test_parse_llm_response_valid():
    ctx = AgentContext(task="t", session_id="s")
    response = "## CODE\ndef f(): pass\n\n## TESTS\ndef test_f(): f()"
    code, tests = ctx.parse_llm_response(response)
    assert "def f(): pass" in code
    assert "def test_f(): f()" in tests

def test_parse_llm_response_missing_sections():
    ctx = AgentContext(task="t", session_id="s")
    code, tests = ctx.parse_llm_response("some random text")
    assert code == ""
    assert tests == ""

def test_update_history():
    ctx = AgentContext(task="t", session_id="s")
    ctx.update_history("TypeError", "added type check", "failed")
    assert len(ctx.iteration_history) == 1
    assert ctx.iteration_history[0].error_type == "TypeError"
    assert ctx.iteration_history[0].iteration == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_agent_context.py -v
# Expected: ImportError
```

- [ ] **Step 3: Create `backend/agent/agent_context.py`**

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class IterationSummary:
    iteration: int
    error_type: str
    fix_attempted: str
    result: str

@dataclass
class AgentContext:
    task: str
    session_id: str
    current_code: Optional[str] = None
    current_tests: Optional[str] = None
    current_error: Optional[str] = None
    current_analysis: Optional[str] = None
    iteration_history: list[IterationSummary] = field(default_factory=list)
    max_iterations: int = 5

    def build_generator_prompt(self) -> tuple[str, str]:
        system = (
            "You are an expert Python developer. "
            "When given a task, respond with ONLY two clearly labelled sections:\n"
            "## CODE\n<the Python function>\n\n## TESTS\n<pytest test functions>\n"
            "No explanation. No markdown fences. Just the two sections."
        )
        user = f"Task: {self.task}"
        if self.iteration_history:
            last = self.iteration_history[-1]
            user += (
                f"\n\nPrevious attempt failed.\n"
                f"Error type: {last.error_type}\n"
                f"What was tried: {last.fix_attempted}\n"
                f"Fix it."
            )
        return system, user

    def build_analyzer_prompt(self, relevant_memories: list) -> tuple[str, str]:
        system = (
            "You are a debugging expert. Analyse the test failure and identify the root cause. "
            "Be concise — one paragraph maximum."
        )
        memory_text = ""
        if relevant_memories:
            memory_text = "\n\nSimilar past mistakes from memory:\n"
            for m in relevant_memories:
                memory_text += f"- {m['error_text']} → fixed by: {m['fix_attempts'][-1]['fix_text']}\n"

        user = (
            f"Task: {self.task}\n\n"
            f"Code that failed:\n{self.current_code}\n\n"
            f"Test output:\n{self.current_error}"
            f"{memory_text}"
        )
        return system, user

    def build_patcher_prompt(self, relevant_memories: list) -> tuple[str, str]:
        system = (
            "You are an expert Python developer fixing buggy code. "
            "Respond with ONLY two clearly labelled sections:\n"
            "## CODE\n<fixed Python function>\n\n## TESTS\n<pytest test functions>\n"
            "No explanation. No markdown fences."
        )
        history_text = ""
        if self.iteration_history:
            history_text = "\n\nIteration history:\n"
            for h in self.iteration_history:
                history_text += f"- Iteration {h.iteration}: tried '{h.fix_attempted}' → {h.result}\n"

        memory_text = ""
        if relevant_memories:
            memory_text = "\n\nKnown fixes for similar mistakes:\n"
            for m in relevant_memories:
                memory_text += f"- {m['error_text']} → {m['fix_attempts'][-1]['fix_text']}\n"

        user = (
            f"Task: {self.task}\n\n"
            f"Broken code:\n{self.current_code}\n\n"
            f"Root cause:\n{self.current_analysis}"
            f"{history_text}"
            f"{memory_text}"
        )
        return system, user

    def update_history(self, error_type: str, fix_attempted: str, result: str):
        self.iteration_history.append(IterationSummary(
            iteration=len(self.iteration_history) + 1,
            error_type=error_type,
            fix_attempted=fix_attempted,
            result=result,
        ))

    def parse_llm_response(self, response: str) -> tuple[str, str]:
        code, tests = "", ""
        if "## CODE" in response and "## TESTS" in response:
            parts = response.split("## TESTS")
            code = parts[0].replace("## CODE", "").strip()
            tests = parts[1].strip()
        return code, tests
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_agent_context.py -v
# Expected: 8 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/agent/agent_context.py backend/tests/test_agent_context.py
git commit -m "feat: AgentContext with prompt builders and response parser"
```

---

## Task 6: Memory Store

**Files:**
- Create: `backend/agent/memory_store.py`
- Create: `backend/tests/test_memory_store.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_memory_store.py`:

```python
import pytest
import json
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from agent.memory_store import get_relevant_memories, save_memory, _get_fix_attempts

def make_pool(rows=None, lastrowid=1):
    """Build a mock aiomysql pool that returns the given rows from fetchall."""
    cursor = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=rows or [])
    cursor.lastrowid = lastrowid
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=False)

    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cursor)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool, cursor

@pytest.mark.asyncio
async def test_get_relevant_memories_empty_db():
    pool, _ = make_pool(rows=[])
    result = await get_relevant_memories("some error", [0.1] * 384, pool)
    assert result == []

@pytest.mark.asyncio
async def test_get_relevant_memories_below_threshold():
    embedding = np.zeros(384).tolist()
    stored = np.ones(384)
    stored_norm = (stored / np.linalg.norm(stored)).tolist()
    rows = [(1, "stored error", json.dumps(stored_norm), 0)]
    pool, _ = make_pool(rows=rows)
    query = np.zeros(384)
    query[0] = 1.0
    result = await get_relevant_memories("error", query.tolist(), pool, threshold=0.99)
    assert result == []

@pytest.mark.asyncio
async def test_get_relevant_memories_above_threshold():
    vec = np.ones(384)
    vec = (vec / np.linalg.norm(vec)).tolist()
    rows = [(1, "stored error", json.dumps(vec), 2)]
    pool, cursor = make_pool(rows=rows)
    cursor.fetchall = AsyncMock(side_effect=[rows, [("fix text", "passed")]])
    result = await get_relevant_memories("error", vec, pool, threshold=0.5)
    assert len(result) == 1
    assert result[0]["id"] == 1
    assert result[0]["similarity"] > 0.5

@pytest.mark.asyncio
async def test_save_memory_new_entry():
    pool, cursor = make_pool(rows=[])
    cursor.fetchall = AsyncMock(return_value=[])
    cursor.lastrowid = 42
    await save_memory("new error", [0.1] * 384, "try this fix", "failed", pool)
    assert cursor.execute.called

@pytest.mark.asyncio
async def test_get_fix_attempts_returns_list():
    rows = [("fix one", "failed"), ("fix two", "passed")]
    pool, _ = make_pool(rows=rows)
    result = await _get_fix_attempts(1, pool)
    assert len(result) == 2
    assert result[0]["fix_text"] == "fix one"
    assert result[1]["result"] == "passed"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_memory_store.py -v
# Expected: ImportError
```

- [ ] **Step 3: Create `backend/agent/memory_store.py`**

```python
import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

async def get_relevant_memories(
    error_text: str,
    embedding: list[float],
    pool,
    top_k: int = 3,
    threshold: float = 0.6,
) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, error_text, embedding, success_count FROM memories"
            )
            rows = await cur.fetchall()

    if not rows:
        return []

    stored_embeddings = np.array([json.loads(r[2]) for r in rows])
    query_vec = np.array(embedding).reshape(1, -1)
    similarities = cosine_similarity(query_vec, stored_embeddings)[0]

    results = []
    for i, (mem_id, error_text_stored, _, success_count) in enumerate(rows):
        if similarities[i] >= threshold:
            results.append({
                "id": mem_id,
                "error_text": error_text_stored,
                "similarity": float(similarities[i]),
                "success_count": success_count,
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    enriched = []
    for r in results[:top_k]:
        r["fix_attempts"] = await _get_fix_attempts(r["id"], pool)
        enriched.append(r)
    return enriched

async def save_memory(
    error_text: str,
    embedding: list[float],
    fix_text: str,
    result: str,
    pool,
    dedup_threshold: float = 0.85,
) -> None:
    existing = await get_relevant_memories(
        error_text, embedding, pool, top_k=1, threshold=dedup_threshold
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if existing:
                mem_id = existing[0]["id"]
                await cur.execute(
                    "INSERT INTO fix_attempts (memory_id, fix_text, result) VALUES (%s, %s, %s)",
                    (mem_id, fix_text, result),
                )
                if result == "passed":
                    await cur.execute(
                        "UPDATE memories SET success_count = success_count + 1 WHERE id = %s",
                        (mem_id,),
                    )
            else:
                await cur.execute(
                    "INSERT INTO memories (error_text, embedding) VALUES (%s, %s)",
                    (error_text, json.dumps(embedding)),
                )
                mem_id = cur.lastrowid
                await cur.execute(
                    "INSERT INTO fix_attempts (memory_id, fix_text, result) VALUES (%s, %s, %s)",
                    (mem_id, fix_text, result),
                )

async def _get_fix_attempts(memory_id: int, pool) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT fix_text, result FROM fix_attempts WHERE memory_id = %s ORDER BY id DESC LIMIT 5",
                (memory_id,),
            )
            rows = await cur.fetchall()
    return [{"fix_text": r[0], "result": r[1]} for r in rows]
```

- [ ] **Step 4: Add `pytest-asyncio` config to `backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_memory_store.py -v
# Expected: 5 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/agent/memory_store.py backend/tests/test_memory_store.py backend/pytest.ini
git commit -m "feat: semantic memory store with cosine similarity and dedup"
```

---

## Task 7: Agent Loop

**Files:**
- Create: `backend/agent/agent_loop.py`
- Create: `backend/tests/test_agent_loop.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_agent_loop.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

def make_mock_pool():
    cursor = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=[])
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=False)
    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cursor)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool

@pytest.mark.asyncio
async def test_run_agent_yields_status_event():
    model = MagicMock()
    model.encode = MagicMock(return_value=[[0.1] * 384])
    pool = make_mock_pool()

    async def fake_stream(system, user, temperature=0.2):
        yield "## CODE\ndef fib(n): return n\n\n## TESTS\ndef test_fib():\n    assert fib(1) == 1\n"

    with patch("agent.agent_loop.call_llm_stream", fake_stream), \
         patch("agent.agent_loop.call_llm", AsyncMock(return_value="root cause")), \
         patch("agent.agent_loop.run_tests") as mock_run, \
         patch("agent.agent_loop.get_relevant_memories", AsyncMock(return_value=[])), \
         patch("agent.agent_loop.save_memory", AsyncMock()):
        from agent.test_executor import TestResult
        mock_run.return_value = TestResult(passed=True, output="1 passed", error_type="", error_summary="")

        from agent.agent_loop import run_agent
        events = []
        async for event in run_agent("Write fib", "sess-1", model, pool):
            events.append(event)

    types = [e["type"] for e in events]
    assert "status" in types
    assert "complete" in types
    complete = next(e for e in events if e["type"] == "complete")
    assert complete["status"] == "passed"

@pytest.mark.asyncio
async def test_run_agent_fails_then_completes():
    model = MagicMock()
    model.encode = MagicMock(return_value=[[0.0] * 384])
    pool = make_mock_pool()

    async def fake_stream(system, user, temperature=0.2):
        yield "## CODE\ndef fib(n): return 0\n\n## TESTS\ndef test_fib():\n    assert fib(1) == 1\n"

    call_count = {"n": 0}

    def run_tests_side_effect(code, tests):
        from agent.test_executor import TestResult
        call_count["n"] += 1
        if call_count["n"] == 1:
            return TestResult(passed=False, output="AssertionError", error_type="AssertionError", error_summary="assert 0 == 1")
        return TestResult(passed=True, output="1 passed", error_type="", error_summary="")

    with patch("agent.agent_loop.call_llm_stream", fake_stream), \
         patch("agent.agent_loop.call_llm", AsyncMock(return_value="## CODE\ndef fib(n): return n\n\n## TESTS\ndef test_fib():\n    assert fib(1) == 1\n")), \
         patch("agent.agent_loop.run_tests", side_effect=run_tests_side_effect), \
         patch("agent.agent_loop.get_relevant_memories", AsyncMock(return_value=[])), \
         patch("agent.agent_loop.save_memory", AsyncMock()):

        from agent.agent_loop import run_agent
        events = []
        async for event in run_agent("Write fib", "sess-2", model, pool):
            events.append(event)

    types = [e["type"] for e in events]
    assert "iteration_failed" in types
    assert "complete" in types
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_agent_loop.py -v
# Expected: ImportError (module not created yet)
```

- [ ] **Step 3: Create `backend/agent/agent_loop.py`**

```python
from typing import AsyncGenerator
from agent.agent_context import AgentContext
from agent.llm_client import call_llm, call_llm_stream
from agent.test_executor import run_tests
from agent.memory_store import get_relevant_memories, save_memory

async def run_agent(
    task: str,
    session_id: str,
    model,
    pool,
) -> AsyncGenerator[dict, None]:

    context = AgentContext(task=task, session_id=session_id)

    for iteration in range(1, context.max_iterations + 1):

        system, user = context.build_generator_prompt()
        full_response = ""

        yield {"type": "status", "iteration": iteration, "message": "Generating code..."}

        async for token in call_llm_stream(system, user):
            full_response += token
            yield {"type": "token", "iteration": iteration, "token": token}

        code, tests = context.parse_llm_response(full_response)
        context.current_code  = code
        context.current_tests = tests

        yield {"type": "status", "iteration": iteration, "message": "Running tests..."}
        test_result = run_tests(code, tests)

        if test_result.passed:
            yield {
                "type": "complete",
                "iteration": iteration,
                "code": code,
                "tests": tests,
                "test_output": test_result.output,
                "status": "passed",
                "total_iterations": iteration,
            }
            return

        context.current_error = test_result.output
        error_embedding = model.encode([test_result.output])[0].tolist()

        relevant_memories = await get_relevant_memories(
            test_result.output, error_embedding, pool
        )

        similarity_score = relevant_memories[0]["similarity"] if relevant_memories else None

        yield {
            "type": "iteration_failed",
            "iteration": iteration,
            "code": code,
            "test_output": test_result.output,
            "error_type": test_result.error_type,
            "status": "failed",
            "similarity_score": similarity_score,
            "memory_hit": len(relevant_memories) > 0,
        }

        yield {"type": "status", "iteration": iteration, "message": "Analyzing error..."}
        sys_a, usr_a = context.build_analyzer_prompt(relevant_memories)
        analysis = await call_llm(sys_a, usr_a, model="gpt-4o-mini")
        context.current_analysis = analysis

        yield {"type": "status", "iteration": iteration, "message": "Generating fix..."}
        sys_p, usr_p = context.build_patcher_prompt(relevant_memories)
        patched = await call_llm(sys_p, usr_p, model="gpt-4o")
        patched_code, patched_tests = context.parse_llm_response(patched)

        await save_memory(
            error_text=test_result.output,
            embedding=error_embedding,
            fix_text=analysis[:300],
            result="failed",
            pool=pool,
        )

        context.update_history(
            error_type=test_result.error_type,
            fix_attempted=analysis[:150],
            result="failed",
        )

        context.current_code  = patched_code
        context.current_tests = patched_tests

    yield {
        "type": "max_iterations_reached",
        "message": f"Could not solve task in {context.max_iterations} iterations.",
        "last_code": context.current_code,
        "last_error": context.current_error,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_agent_loop.py -v
# Expected: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/agent/agent_loop.py backend/tests/test_agent_loop.py
git commit -m "feat: agent loop orchestrating generator, analyzer, patcher with memory"
```

---

## Task 8: FastAPI Backend

**Files:**
- Create: `backend/api.py`
- Create: `backend/Dockerfile`

- [ ] **Step 1: Create `backend/api.py`**

```python
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer
from db.connection import get_pool, close_pool
from agent.agent_loop import run_agent

_model: SentenceTransformer = None
_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model, _pool
    print("Loading embedding model...")
    _model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Connecting to database...")
    _pool = await get_pool()
    print("Ready.")
    yield
    await close_pool()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws/run")
async def run_agent_ws(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())

    try:
        data = await websocket.receive_json()
        task = data.get("task", "").strip()

        if not task:
            await websocket.send_json({"type": "error", "message": "Task cannot be empty."})
            return

        async for event in run_agent(task, session_id, _model, _pool):
            await websocket.send_json(event)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
```

- [ ] **Step 2: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

- [ ] **Step 3: Test the health endpoint locally**

```bash
cd backend
pip install -r requirements.txt
# start MySQL via docker first: docker compose up db -d
uvicorn api:app --reload &
curl http://localhost:8000/health
# Expected: {"status":"ok"}
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add backend/api.py backend/Dockerfile
git commit -m "feat: FastAPI app with WebSocket /ws/run and lifespan model loading"
```

---

## Task 9: Frontend Setup

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/src/main.jsx`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "self-improving-agent-ui",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "@monaco-editor/react": "^4.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.14",
    "vite": "^5.4.10"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.js`**

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
})
```

- [ ] **Step 3: Create `frontend/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

- [ ] **Step 4: Create `frontend/postcss.config.js`**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 5: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Self-Improving Agent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Create `frontend/src/main.jsx`**

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 7: Create `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 8: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 9: Install dependencies and verify dev server starts**

```bash
cd frontend
npm install
npm run dev
# Expected: Vite dev server running at http://localhost:5173
# Ctrl+C to stop
```

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "feat: frontend Vite + React + Tailwind scaffold with Dockerfile"
```

---

## Task 10: WebSocket Hook

**Files:**
- Create: `frontend/src/hooks/useAgentSocket.js`

- [ ] **Step 1: Create `frontend/src/hooks/useAgentSocket.js`**

```javascript
import { useState, useCallback, useRef } from "react";

export function useAgentSocket() {
  const [iterations, setIterations]   = useState([]);
  const [status, setStatus]           = useState("idle");
  const [streamingCode, setStreaming] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const wsRef = useRef(null);

  const runAgent = useCallback((task) => {
    if (wsRef.current) wsRef.current.close();

    setIterations([]);
    setStreaming("");
    setStatus("running");
    setStatusMessage("");

    const ws = new WebSocket("ws://localhost:8000/ws/run");
    wsRef.current = ws;

    ws.onopen = () => ws.send(JSON.stringify({ task }));

    ws.onmessage = (e) => {
      const event = JSON.parse(e.data);

      if (event.type === "token") {
        setStreaming(prev => prev + event.token);
        return;
      }
      if (event.type === "status") {
        setStatusMessage(event.message);
        return;
      }
      if (event.type === "iteration_failed") {
        setIterations(prev => [...prev, event]);
        setStreaming("");
        return;
      }
      if (event.type === "complete") {
        setIterations(prev => [...prev, event]);
        setStatus("complete");
        setStreaming("");
        return;
      }
      if (event.type === "max_iterations_reached") {
        setStatus("error");
        setStreaming("");
        return;
      }
      if (event.type === "error") {
        setStatus("error");
        return;
      }
    };

    ws.onclose = () => {
      setStatus(prev => prev === "running" ? "idle" : prev);
    };
  }, []);

  const stop = useCallback(() => {
    if (wsRef.current) wsRef.current.close();
    setStatus("idle");
  }, []);

  return { iterations, status, streamingCode, statusMessage, runAgent, stop };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useAgentSocket.js
git commit -m "feat: WebSocket hook managing iteration state and streaming"
```

---

## Task 11: Frontend Components

**Files:**
- Create: `frontend/src/components/TaskInput.jsx`
- Create: `frontend/src/components/CodePanel.jsx`
- Create: `frontend/src/components/IterationCard.jsx`
- Create: `frontend/src/components/IterationFeed.jsx`
- Create: `frontend/src/components/MemoryLog.jsx`
- Create: `frontend/src/App.jsx`

- [ ] **Step 1: Create `frontend/src/components/TaskInput.jsx`**

```jsx
export default function TaskInput({ task, setTask, onRun, onStop, status }) {
  const isRunning = status === "running";

  return (
    <div className="flex flex-col gap-3">
      <label className="text-sm font-medium text-gray-300">Coding Task</label>
      <textarea
        value={task}
        onChange={e => setTask(e.target.value)}
        disabled={isRunning}
        placeholder="e.g. Write a function that returns the nth Fibonacci number."
        className="w-full h-32 bg-gray-900 border border-gray-700 rounded-lg p-3 text-sm text-gray-100 placeholder-gray-500 resize-none focus:outline-none focus:border-blue-500 disabled:opacity-50"
      />
      <div className="flex gap-2">
        <button
          onClick={onRun}
          disabled={isRunning || !task.trim()}
          className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium py-2 px-4 rounded-lg transition-colors"
        >
          {isRunning ? "Running..." : "Run Agent"}
        </button>
        {isRunning && (
          <button
            onClick={onStop}
            className="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium py-2 px-4 rounded-lg transition-colors"
          >
            Stop
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/CodePanel.jsx`**

```jsx
import Editor from "@monaco-editor/react";

export default function CodePanel({ code, language = "python" }) {
  return (
    <div className="rounded-lg overflow-hidden border border-gray-700">
      <Editor
        height="300px"
        language={language}
        value={code || ""}
        theme="vs-dark"
        options={{
          readOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          lineNumbers: "on",
          padding: { top: 8, bottom: 8 },
        }}
      />
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/IterationCard.jsx`**

```jsx
import { useState } from "react";
import CodePanel from "./CodePanel";

export default function IterationCard({ event }) {
  const [showTests, setShowTests] = useState(false);
  const passed = event.status === "passed";

  return (
    <div className="border border-gray-800 rounded-xl bg-gray-900 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800">
        <span className="text-gray-400 text-sm font-mono">Iteration {event.iteration}</span>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
          passed
            ? "bg-green-900 text-green-300"
            : "bg-red-900 text-red-300"
        }`}>
          {passed ? "PASSED" : "FAILED"}
        </span>
        {event.memory_hit && event.similarity_score != null && (
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-900 text-blue-300">
            Memory match: {(event.similarity_score * 100).toFixed(1)}%
          </span>
        )}
        {!passed && event.error_type && (
          <span className="ml-auto text-xs text-gray-500 font-mono">{event.error_type}</span>
        )}
      </div>

      {/* Code */}
      <div className="p-4">
        <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Generated Code</p>
        <CodePanel code={event.code} />
      </div>

      {/* Test output */}
      <div className="px-4 pb-4">
        <button
          onClick={() => setShowTests(v => !v)}
          className="text-xs text-gray-500 hover:text-gray-300 mb-2 transition-colors"
        >
          {showTests ? "▼" : "▶"} Test Output
        </button>
        {showTests && (
          <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-gray-300 overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap">
            {event.test_output}
          </pre>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/components/IterationFeed.jsx`**

```jsx
import IterationCard from "./IterationCard";
import CodePanel from "./CodePanel";

export default function IterationFeed({ iterations, streamingCode, status, statusMessage }) {
  const isEmpty = iterations.length === 0 && !streamingCode;

  return (
    <div className="flex flex-col gap-4">
      {isEmpty && status === "idle" && (
        <div className="text-center text-gray-600 mt-20 text-sm">
          Enter a task and click Run Agent to start.
        </div>
      )}

      {iterations.map((event, i) => (
        <IterationCard key={i} event={event} />
      ))}

      {/* Live streaming card */}
      {streamingCode && (
        <div className="border border-blue-800 rounded-xl bg-gray-900 overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-blue-800">
            <span className="text-gray-400 text-sm font-mono">
              Iteration {iterations.length + 1}
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-900 text-blue-300 animate-pulse">
              GENERATING
            </span>
            {statusMessage && (
              <span className="text-xs text-gray-500 ml-auto">{statusMessage}</span>
            )}
          </div>
          <div className="p-4">
            <CodePanel code={streamingCode} />
          </div>
        </div>
      )}

      {status === "complete" && (
        <div className="text-center text-green-400 text-sm py-4">
          ✓ All tests passed
        </div>
      )}
      {status === "error" && (
        <div className="text-center text-red-400 text-sm py-4">
          Max iterations reached — could not solve the task.
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create `frontend/src/components/MemoryLog.jsx`**

```jsx
import { useState, useEffect } from "react";

export default function MemoryLog() {
  const [open, setOpen] = useState(false);
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchMemories = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/memories");
      if (res.ok) {
        const data = await res.json();
        setMemories(data);
      }
    } catch {
      // backend may not expose this endpoint yet
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) fetchMemories();
  }, [open]);

  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-400 hover:text-gray-200 transition-colors"
      >
        <span>Memory Log</span>
        <span>{open ? "▼" : "▶"}</span>
      </button>

      {open && (
        <div className="border-t border-gray-800 p-3 max-h-64 overflow-y-auto">
          {loading && <p className="text-xs text-gray-500">Loading...</p>}
          {!loading && memories.length === 0 && (
            <p className="text-xs text-gray-600">No memories stored yet.</p>
          )}
          {memories.map((m, i) => (
            <div key={i} className="mb-3 pb-3 border-b border-gray-800 last:border-0">
              <p className="text-xs text-gray-400 line-clamp-2">{m.error_text}</p>
              <p className="text-xs text-gray-600 mt-1">
                {m.success_count} successful fix{m.success_count !== 1 ? "es" : ""}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Create `frontend/src/App.jsx`**

```jsx
import { useState } from "react";
import TaskInput     from "./components/TaskInput";
import IterationFeed from "./components/IterationFeed";
import MemoryLog     from "./components/MemoryLog";
import { useAgentSocket } from "./hooks/useAgentSocket";

export default function App() {
  const { iterations, status, streamingCode, statusMessage, runAgent, stop } = useAgentSocket();
  const [task, setTask] = useState("");

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
        <span className="text-blue-400 font-semibold text-lg">Self-Improving Agent</span>
        <span className="text-gray-500 text-sm">Aiden AI Hackathon</span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-96 border-r border-gray-800 flex flex-col p-4 gap-4">
          <TaskInput
            task={task}
            setTask={setTask}
            onRun={() => runAgent(task)}
            onStop={stop}
            status={status}
          />
          <MemoryLog />
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <IterationFeed
            iterations={iterations}
            streamingCode={streamingCode}
            status={status}
            statusMessage={statusMessage}
          />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Verify the dev server renders without errors**

```bash
cd frontend
npm run dev
# Open http://localhost:5173 — should show the two-panel layout with no console errors
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat: React UI with TaskInput, IterationFeed, IterationCard, CodePanel, MemoryLog"
```

---

## Task 12: Memory API Endpoint (Optional — enables MemoryLog)

**Files:**
- Modify: `backend/api.py` — add `GET /memories` endpoint

- [ ] **Step 1: Add `/memories` endpoint to `backend/api.py`**

Append after the `/health` route:

```python
@app.get("/memories")
async def list_memories():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, error_text, success_count, created_at FROM memories ORDER BY id DESC LIMIT 50"
            )
            rows = await cur.fetchall()
    return [
        {"id": r[0], "error_text": r[1], "success_count": r[2], "created_at": str(r[3])}
        for r in rows
    ]
```

- [ ] **Step 2: Test the endpoint**

```bash
cd backend
uvicorn api:app --reload &
curl http://localhost:8000/memories
# Expected: [] (empty array if no memories yet)
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add backend/api.py
git commit -m "feat: GET /memories endpoint for MemoryLog UI panel"
```

---

## Task 13: End-to-End Smoke Test

- [ ] **Step 1: Start all services**

```bash
docker compose up --build -d
docker compose ps
# All three services should be healthy/running
```

- [ ] **Step 2: Test the health endpoint**

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

- [ ] **Step 3: Run the demo task via wscat (or Postman)**

```bash
npm install -g wscat
wscat -c ws://localhost:8000/ws/run
# Once connected, send:
{"task": "Write a function that returns the nth Fibonacci number."}
# Watch the stream: token events, then iteration_failed or complete
```

- [ ] **Step 4: Open the UI and verify**

- Open `http://localhost:5173`
- Enter: `Write a function that returns the nth Fibonacci number.`
- Click Run Agent
- Verify: streaming code appears, then iteration card(s) show up with PASSED/FAILED badges
- If iteration fails: verify memory_hit badge appears on second run with similar task

- [ ] **Step 5: Run the demo second task to verify memory match**

```
Write a function that finds the nth element in a list starting from 1.
```
- Expected: blue "Memory match: XX%" badge appears in the UI on the first failure

- [ ] **Step 6: Run all backend tests**

```bash
cd backend
python -m pytest tests/ -v
# Expected: all tests pass
```

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "chore: end-to-end verified, all tests passing"
```

---

## Notes for Implementation

- **pytest-asyncio**: `asyncio_mode = auto` in `pytest.ini` is required for async test functions to work without decorators
- **Model loading**: `SentenceTransformer('all-MiniLM-L6-v2')` downloads ~80MB on first run — this is cached in Docker layer after first build
- **DB first**: always `docker compose up db -d` before running the backend locally; the pool will fail to connect otherwise
- **CORS**: the FastAPI CORS middleware allows `http://localhost:5173` only — if the frontend port changes, update `api.py`
- **4 uvicorn workers**: each worker loads the embedding model independently; `--workers 4` means ~400MB RAM for models alone
