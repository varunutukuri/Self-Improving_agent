import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from agent.memory_store import (
    _get_fix_attempts,
    get_relevant_memories,
    save_memory,
    update_last_similarity,
)


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
async def test_save_memory_dedup_does_not_touch_last_similarity():
    """
    A dedup match compares a memory against a near-identical copy of itself, so
    its score is ~1.0 regardless of usefulness. Writing that to last_similarity
    would pin every row to 100% in the UI. Only retrieval scores belong there.
    """
    vec = (np.ones(384) / np.linalg.norm(np.ones(384))).tolist()
    rows = [(1, "stored error", json.dumps(vec), 0)]
    pool, cursor = make_pool(rows=rows)
    cursor.fetchall = AsyncMock(side_effect=[rows, [("prior fix", "failed")]])

    await save_memory("stored error", vec, "a fix", "passed", pool)

    statements = " ".join(str(c) for c in cursor.execute.call_args_list)
    assert "last_similarity" not in statements
    assert "success_count = success_count + 1" in statements


@pytest.mark.asyncio
async def test_update_last_similarity_writes_retrieval_score():
    """The retrieval score is what the UI similarity column should reflect."""
    pool, cursor = make_pool(rows=[])
    await update_last_similarity(7, 0.681, pool)

    args = cursor.execute.call_args
    assert "UPDATE memories SET last_similarity" in args[0][0]
    assert args[0][1] == (0.681, 7)


@pytest.mark.asyncio
async def test_get_fix_attempts_returns_list():
    rows = [("fix one", "failed"), ("fix two", "passed")]
    pool, _ = make_pool(rows=rows)
    result = await _get_fix_attempts(1, pool)
    assert len(result) == 2
    assert result[0]["fix_text"] == "fix one"
    assert result[1]["result"] == "passed"
