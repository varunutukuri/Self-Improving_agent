"""
agent_loop.py
-------------
Core async generator that drives the generate → test → analyse → patch loop.

Each iteration yields structured event dicts that are forwarded to the
WebSocket client so the UI can update in real time.

Event types emitted
-------------------
status             — phase change message (e.g. "Running tests...")
token              — one streamed LLM token for the live code editor
iteration_failed   — iteration result with per-test cases; critic rows arrive
                     separately via iteration_analysis once LLM analysis is done
iteration_analysis — structured critic output: error_class, root_cause, fix_hint
memory_saved       — a memory row was just written; UI should refetch /memories
complete           — all tests passed; includes final code + per-test cases
max_iterations_reached — agent exhausted all retries

Memory write policy
-------------------
Every failure is written with result="failed".  When a later iteration passes,
the *preceding* failure is written again with result="passed", which dedups onto
the same memory row and increments its success_count.  This is what makes the
store a record of fixes that worked rather than only of approaches that didn't.
"""
import asyncio
import json
from typing import AsyncGenerator

from agent.agent_context import AgentContext
from agent.llm_client import call_llm, call_llm_stream
from agent.memory_store import get_relevant_memories, save_memory, update_last_similarity
from agent.test_executor import run_tests

# Max chars of analysis text stored in the memory store / history
_FIX_TEXT_MAX_CHARS      = 300
_HISTORY_TEXT_MAX_CHARS  = 150


async def run_agent(
    task: str,
    session_id: str,
    model,
    pool,
    max_iterations: int = 5,
) -> AsyncGenerator[dict, None]:
    """
    Drive the self-improving agent loop for *task*.

    Parameters
    ----------
    task:           Natural-language coding task.
    session_id:     Unique ID for this agent run.
    model:          Loaded SentenceTransformer instance (from api.py lifespan).
    pool:           aiomysql connection pool (from api.py lifespan).
    max_iterations: Maximum number of generate → test → patch cycles.
    """
    context = AgentContext(task=task, session_id=session_id, max_iterations=max_iterations)

    # Carries the most recent failure forward so that, when a later iteration
    # passes, the fix that actually worked can be written back to memory with
    # result="passed".  None until the first failure occurs.
    pending_failure: dict | None = None

    for iteration in range(1, context.max_iterations + 1):

        # ------------------------------------------------------------------ #
        # Stage 1: Generate code via streaming LLM call                       #
        # ------------------------------------------------------------------ #
        if iteration == 1:
            yield {"type": "status", "iteration": iteration, "message": "Generating code..."}
            system, user = context.build_generator_prompt()
        else:
            yield {"type": "status", "iteration": iteration, "message": "Generating fix..."}
            system, user = context.build_patcher_prompt(context.current_memories)

        full_response = ""
        async for token in call_llm_stream(system, user):
            full_response += token
            yield {"type": "token", "iteration": iteration, "token": token}

        code, tests = context.parse_llm_response(full_response)
        context.current_code  = code
        context.current_tests = tests

        # ------------------------------------------------------------------ #
        # Stage 2: Run pytest in a subprocess                                 #
        # ------------------------------------------------------------------ #
        yield {"type": "status", "iteration": iteration, "message": "Running tests..."}
        # run_tests() is blocking (subprocess.run with a 30s timeout).  Off-loading it
        # to a worker thread keeps the event loop free, so a long-running test run in
        # one session cannot freeze every other WebSocket connection on this worker.
        test_result = await asyncio.to_thread(run_tests, code, tests)

        if test_result.passed:
            # Record the fix that actually worked.  Because the error text is identical
            # to the one already stored, this dedups onto the existing memory row,
            # appends a fix_attempt with result="passed", and increments success_count.
            # Without this the store only ever accumulates failed approaches.
            if pending_failure is not None:
                await save_memory(
                    error_text=pending_failure["error_text"],
                    embedding=pending_failure["embedding"],
                    fix_text=pending_failure["fix_text"],
                    result="passed",
                    pool=pool,
                    error_class=pending_failure["error_class"],
                    root_cause=pending_failure["root_cause"],
                )
                # Signal that the store has changed so the UI refetches AFTER the
                # write, not before it.
                yield {"type": "memory_saved", "iteration": iteration}

            yield {
                "type":             "complete",
                "iteration":        iteration,
                "code":             code,
                "tests":            tests,
                "test_output":      test_result.output,
                "test_cases":       test_result.test_cases,
                "status":           "passed",
                "total_iterations": iteration,
            }
            return

        # ------------------------------------------------------------------ #
        # Stage 3: Retrieve relevant memories for this error                  #
        # ------------------------------------------------------------------ #
        context.current_error = test_result.output

        # Embed the error text to query the memory store
        raw_embedding = model.encode([test_result.output])[0]
        error_embedding: list[float] = (
            raw_embedding.tolist()
            if hasattr(raw_embedding, "tolist")
            else list(raw_embedding)
        )

        relevant_memories = await get_relevant_memories(
            test_result.output, error_embedding, pool
        )
        context.current_memories = relevant_memories
        similarity_score = relevant_memories[0]["similarity"] if relevant_memories else None

        # Stamp each retrieved memory with the score it earned against this NEW
        # error.  This is what the UI's similarity column shows — a real measure
        # of how well the memory generalised, rather than a dedup self-match.
        for memory in relevant_memories:
            await update_last_similarity(memory["id"], memory["similarity"], pool)

        # Emit the iteration result immediately so the UI card appears
        yield {
            "type":             "iteration_failed",
            "iteration":        iteration,
            "code":             code,
            "test_output":      test_result.output,
            "test_cases":       test_result.test_cases,
            "error_type":       test_result.error_type,
            "status":           "failed",
            "similarity_score": similarity_score,
            "memory_hit":       len(relevant_memories) > 0,
        }

        # ------------------------------------------------------------------ #
        # Stage 4: Analyse the root cause (LLM returns structured JSON)      #
        # ------------------------------------------------------------------ #
        yield {"type": "status", "iteration": iteration, "message": "Analyzing error..."}

        sys_a, usr_a = context.build_analyzer_prompt(relevant_memories)
        analysis_raw = await call_llm(sys_a, usr_a, model="gpt-4o-mini")

        # Parse structured JSON from the LLM; fall back gracefully on bad output
        try:
            analysis_data = json.loads(analysis_raw)
            error_class = analysis_data.get("error_class", test_result.error_type)
            root_cause  = analysis_data.get("root_cause",  analysis_raw[:200])
            fix_hint    = analysis_data.get("fix_hint",    "")
        except (json.JSONDecodeError, AttributeError):
            error_class = test_result.error_type
            root_cause  = analysis_raw[:200]
            fix_hint    = ""

        context.current_analysis = root_cause

        # Emit the structured critic output — the UI patches it onto the card
        yield {
            "type":        "iteration_analysis",
            "iteration":   iteration,
            "error_class": error_class,
            "root_cause":  root_cause,
            "fix_hint":    fix_hint,
        }

        # ------------------------------------------------------------------ #
        # Stage 5: Record history & save to memory store                     #
        # ------------------------------------------------------------------ #
        fix_text = fix_hint[:_FIX_TEXT_MAX_CHARS] or root_cause[:_FIX_TEXT_MAX_CHARS]

        # Persist the error + attempted fix in the memory store
        await save_memory(
            error_text=test_result.output,
            embedding=error_embedding,
            fix_text=fix_text,
            result="failed",
            pool=pool,
            error_class=error_class,
            root_cause=root_cause,
        )

        # The row now exists — tell the UI to refetch.  This must come after
        # save_memory(), not after iteration_failed, or the table queries the
        # database before the write lands and renders one step behind.
        yield {"type": "memory_saved", "iteration": iteration}

        # Carry this failure forward.  If the next iteration passes, the same error
        # is re-saved with result="passed" so the memory records the winning fix.
        pending_failure = {
            "error_text":  test_result.output,
            "embedding":   error_embedding,
            "fix_text":    fix_text,
            "error_class": error_class,
            "root_cause":  root_cause,
        }

        # Record what was tried so the next patcher prompt can reference it
        context.update_history(
            error_type=test_result.error_type,
            fix_attempted=root_cause[:_HISTORY_TEXT_MAX_CHARS],
            result="failed",
        )

    # All iterations exhausted without a passing result
    yield {
        "type":       "max_iterations_reached",
        "message":    f"Could not solve task in {context.max_iterations} iterations.",
        "last_code":  context.current_code,
        "last_error": context.current_error,
    }
