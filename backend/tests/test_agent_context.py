from agent.agent_context import AgentContext


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
    # The new prompt requests structured JSON with error_class / root_cause / fix_hint
    assert "error_class" in system
    assert "root_cause" in system
    assert "fix_hint" in system
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
