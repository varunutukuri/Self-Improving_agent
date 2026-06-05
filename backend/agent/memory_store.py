import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# NOTE: the SentenceTransformer model is loaded ONCE in api.py lifespan
# and passed into these functions — never load it here

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
