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
