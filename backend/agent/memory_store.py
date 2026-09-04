"""
memory_store.py
---------------
Async helpers for reading and writing to the ``memories`` / ``fix_attempts``
tables in MySQL.

Design note
-----------
Similarity search is performed in Python (via scikit-learn cosine_similarity)
because MySQL does not natively support vector similarity queries.  The full
memories table is loaded into RAM on each search call.  This is acceptable for
small tables (< ~10 k rows) but should be replaced with a dedicated vector
store (e.g. pgvector or Pinecone) if the dataset grows significantly.
"""
import json
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


async def get_relevant_memories(
    query_error_text: str,
    embedding: list[float],
    pool,
    top_k: int = 3,
    threshold: float = 0.6,
) -> list[dict]:
    """
    Return up to *top_k* memories whose stored embedding is cosine-similar
    to *embedding* above *threshold*.

    Each returned dict has keys:
        ``id``, ``error_text``, ``similarity``, ``success_count``,
        ``fix_attempts`` (list of ``{fix_text, result}`` dicts).

    Parameters
    ----------
    query_error_text: The raw error string from the failed test run.
    embedding:        Float vector produced by SentenceTransformer.encode().
    pool:             aiomysql connection pool.
    top_k:            Maximum number of results to return.
    threshold:        Minimum cosine similarity score to include a result.
    """
    # Fetch every stored memory row
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, error_text, embedding, success_count FROM memories"
            )
            rows = await cur.fetchall()

    if not rows:
        return []

    # Compute cosine similarity between the query vector and all stored vectors
    stored_embeddings = np.array([json.loads(row[2]) for row in rows])
    query_vec         = np.array(embedding).reshape(1, -1)
    similarities      = cosine_similarity(query_vec, stored_embeddings)[0]

    # Collect rows that pass the similarity threshold
    candidates = []
    for i, (mem_id, stored_error_text, _embedding_json, success_count) in enumerate(rows):
        if similarities[i] >= threshold:
            candidates.append({
                "id":            mem_id,
                "error_text":    stored_error_text,
                "similarity":    float(similarities[i]),
                "success_count": success_count,
            })

    # Sort by descending similarity and enrich with fix-attempt history
    candidates.sort(key=lambda x: x["similarity"], reverse=True)

    enriched = []
    for candidate in candidates[:top_k]:
        candidate["fix_attempts"] = await _get_fix_attempts(candidate["id"], pool)
        enriched.append(candidate)

    return enriched


async def save_memory(
    error_text: str,
    embedding: list[float],
    fix_text: str,
    result: str,
    pool,
    error_class: Optional[str] = None,
    root_cause: Optional[str] = None,
    dedup_threshold: float = 0.85,
) -> None:
    """
    Persist an error + fix attempt to the memory store.

    If a sufficiently similar memory already exists (similarity ≥
    *dedup_threshold*), a new ``fix_attempts`` row is appended to it and its
    ``success_count`` is incremented when *result* is ``"passed"``.
    Otherwise a fresh ``memories`` row is inserted.

    Parameters
    ----------
    error_text:      Raw error output from the failed test.
    embedding:       Float vector for *error_text*.
    fix_text:        Short description of the fix that was attempted.
    result:          ``"passed"`` or ``"failed"``.
    pool:            aiomysql connection pool.
    error_class:     Short LLM-generated label (e.g. ``"off_by_one"``).
    root_cause:      One-sentence root cause from LLM analysis.
    dedup_threshold: Cosine similarity above which two errors are treated as
                     duplicates and merged.
    """
    # Look for an existing memory that matches this error closely
    existing = await get_relevant_memories(
        error_text, embedding, pool, top_k=1, threshold=dedup_threshold
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if existing:
                # Duplicate found — append this attempt to the existing memory.
                #
                # NOTE: last_similarity is deliberately NOT written here. The score
                # for a dedup match is ~1.0 by construction (the error text is
                # near-identical), so recording it would pin every row to 100% and
                # make the column meaningless. It is set by update_last_similarity()
                # at retrieval time instead, where the score is informative.
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
                # New error — create a memory row with structured analysis data
                await cur.execute(
                    "INSERT INTO memories (error_text, embedding, error_class, root_cause) "
                    "VALUES (%s, %s, %s, %s)",
                    (error_text, json.dumps(embedding), error_class, root_cause),
                )
                mem_id = cur.lastrowid
                await cur.execute(
                    "INSERT INTO fix_attempts (memory_id, fix_text, result) VALUES (%s, %s, %s)",
                    (mem_id, fix_text, result),
                )


async def update_last_similarity(memory_id: int, similarity: float, pool) -> None:
    """
    Record the cosine score from the most recent *retrieval* match.

    This is the number worth surfacing in the UI: how closely this stored
    mistake matched a genuinely new error. Deduplication scores are excluded on
    purpose — those compare a memory against a near-identical copy of itself and
    are ~1.0 regardless of how useful the memory is.

    Parameters
    ----------
    memory_id:  Primary key of the ``memories`` row that was retrieved.
    similarity: Cosine similarity between the new error and this memory.
    pool:       aiomysql connection pool.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE memories SET last_similarity = %s WHERE id = %s",
                (similarity, memory_id),
            )


async def _get_fix_attempts(memory_id: int, pool) -> list[dict]:
    """
    Return the most recent fix attempts for a given memory row.

    Parameters
    ----------
    memory_id: Primary key of the ``memories`` row.
    pool:      aiomysql connection pool.

    Returns
    -------
    List of ``{"fix_text": str, "result": str}`` dicts, newest first, up to 5.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT fix_text, result FROM fix_attempts "
                "WHERE memory_id = %s ORDER BY id DESC LIMIT 5",
                (memory_id,),
            )
            rows = await cur.fetchall()

    return [{"fix_text": row[0], "result": row[1]} for row in rows]
