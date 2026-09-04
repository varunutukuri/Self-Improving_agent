from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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


@pytest.mark.asyncio
async def test_successful_fix_is_saved_to_memory_as_passed():
    """
    Regression test: when an iteration passes after an earlier failure, the
    preceding error must be re-saved with result="passed" so the memory records
    the fix that actually worked and success_count is incremented.

    Previously only result="failed" was ever written, leaving success_count at 0
    for every row and making the store a log of approaches that did NOT work.
    """
    model = MagicMock()
    model.encode = MagicMock(return_value=[[0.5] * 384])
    pool = make_mock_pool()

    async def fake_stream(system, user, temperature=0.2):
        yield "## CODE\ndef fib(n): return 0\n\n## TESTS\ndef test_fib():\n    assert fib(1) == 1\n"

    call_count = {"n": 0}

    def run_tests_side_effect(code, tests):
        from agent.test_executor import TestResult
        call_count["n"] += 1
        if call_count["n"] == 1:
            return TestResult(passed=False, output="AssertionError: assert 0 == 1",
                              error_type="AssertionError", error_summary="assert 0 == 1")
        return TestResult(passed=True, output="1 passed", error_type="", error_summary="")

    analysis_json = '{"error_class": "off_by_one", "root_cause": "returns 0", "fix_hint": "return n"}'
    mock_save = AsyncMock()

    with patch("agent.agent_loop.call_llm_stream", fake_stream), \
         patch("agent.agent_loop.call_llm", AsyncMock(return_value=analysis_json)), \
         patch("agent.agent_loop.run_tests", side_effect=run_tests_side_effect), \
         patch("agent.agent_loop.get_relevant_memories", AsyncMock(return_value=[])), \
         patch("agent.agent_loop.save_memory", mock_save):

        from agent.agent_loop import run_agent
        async for _ in run_agent("Write fib", "sess-3", model, pool):
            pass

    results = [c.kwargs["result"] for c in mock_save.call_args_list]
    assert results == ["failed", "passed"], f"expected one of each, got {results}"

    # The passing write must reference the ORIGINAL error, so it dedups onto the
    # existing row rather than creating a new one.
    passed_call = mock_save.call_args_list[-1]
    assert passed_call.kwargs["error_text"] == "AssertionError: assert 0 == 1"
    assert passed_call.kwargs["fix_text"] == "return n"
    assert passed_call.kwargs["error_class"] == "off_by_one"


@pytest.mark.asyncio
async def test_first_iteration_pass_writes_no_memory():
    """A task solved on iteration 1 has no preceding failure, so nothing is saved."""
    model = MagicMock()
    model.encode = MagicMock(return_value=[[0.1] * 384])
    pool = make_mock_pool()

    async def fake_stream(system, user, temperature=0.2):
        yield "## CODE\ndef fib(n): return n\n\n## TESTS\ndef test_fib():\n    assert fib(1) == 1\n"

    mock_save = AsyncMock()

    with patch("agent.agent_loop.call_llm_stream", fake_stream), \
         patch("agent.agent_loop.call_llm", AsyncMock(return_value="{}")), \
         patch("agent.agent_loop.run_tests") as mock_run, \
         patch("agent.agent_loop.get_relevant_memories", AsyncMock(return_value=[])), \
         patch("agent.agent_loop.save_memory", mock_save):
        from agent.test_executor import TestResult
        mock_run.return_value = TestResult(passed=True, output="1 passed",
                                           error_type="", error_summary="")

        from agent.agent_loop import run_agent
        async for _ in run_agent("Write fib", "sess-4", model, pool):
            pass

    mock_save.assert_not_called()
