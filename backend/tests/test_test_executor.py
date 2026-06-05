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
