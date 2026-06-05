"""
api.py
------
FastAPI application entry point.

Lifespan
--------
On startup:
  - Loads the SentenceTransformer embedding model (heavy, ~90 MB).
  - Opens the MySQL connection pool.
On shutdown:
  - Gracefully closes the connection pool so no connections are leaked.

Endpoints
---------
GET  /health      — liveness probe.
GET  /memories    — list the 50 most recent memory entries with their latest fix.
WS   /ws/run      — stream agent events back to the browser.
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer

from db.connection import get_pool, close_pool
from agent.agent_loop import run_agent

# ---------------------------------------------------------------------------
# Module-level singletons — populated by the lifespan handler below.
# ---------------------------------------------------------------------------
_model: SentenceTransformer = None
_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared resources on startup and release them on shutdown."""
    global _model, _pool

    print("Loading embedding model...")
    _model = SentenceTransformer("all-MiniLM-L6-v2")

    print("Connecting to database...")
    _pool = await get_pool()

    print("Ready.")
    yield  # application runs here

    # --- shutdown ---
    await close_pool()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Simple liveness probe."""
    return {"status": "ok"}


@app.get("/memories")
async def list_memories():
    """
    Return the 50 most recently created memory entries, each enriched with
    the latest fix attempt text, error_class, root_cause, and last_similarity.

    Uses the lifespan-managed _pool directly (no second pool creation).
    """
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    m.id,
                    m.error_class,
                    m.root_cause,
                    m.last_similarity,
                    m.success_count,
                    fa.fix_text
                FROM memories m
                LEFT JOIN fix_attempts fa
                    ON fa.id = (
                        SELECT MAX(id)
                        FROM fix_attempts
                        WHERE memory_id = m.id
                    )
                ORDER BY m.id DESC
                LIMIT 50
            """)
            rows = await cur.fetchall()

    return [
        {
            "id":              row[0],
            "error_class":     row[1] or "unknown",
            "root_cause":      row[2] or "",
            "last_similarity": float(row[3]) if row[3] else 0.0,
            "success_count":   row[4],
            "fix_applied":     row[5] or "",
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/run")
async def run_agent_ws(websocket: WebSocket):
    """
    Accept a task over WebSocket, run the agent loop, and stream events back.

    Expected client message (JSON):
        {"task": "<coding task>", "max_iterations": 5}

    Streamed event types: status, token, iteration_failed, iteration_analysis,
    complete, max_iterations_reached, error.
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())

    try:
        data = await websocket.receive_json()
        task = data.get("task", "").strip()

        # Clamp max_iterations between 1 and 10
        max_iterations = int(data.get("max_iterations", 5))
        max_iterations = max(1, min(10, max_iterations))

        if not task:
            await websocket.send_json({"type": "error", "message": "Task cannot be empty."})
            return

        async for event in run_agent(task, session_id, _model, _pool, max_iterations=max_iterations):
            await websocket.send_json(event)

    except WebSocketDisconnect:
        # Client navigated away or closed the tab — nothing to do.
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
