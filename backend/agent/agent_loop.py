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
        raw_embedding = model.encode([test_result.output])[0]
        error_embedding = raw_embedding.tolist() if hasattr(raw_embedding, "tolist") else list(raw_embedding)

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
