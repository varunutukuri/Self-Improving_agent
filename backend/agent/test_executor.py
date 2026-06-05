"""
test_executor.py
----------------
Runs generated code + tests in an isolated subprocess and returns a structured
result.

Security note
-------------
The generated code is executed inside a temporary directory with no extra
sandboxing beyond what the OS provides.  Do **not** run this in a shared
multi-tenant environment without additional isolation (e.g. Docker with
--network=none and resource limits).
"""
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field


@dataclass
class TestResult:
    """
    Outcome of a single pytest run.

    Attributes
    ----------
    passed:        True when pytest exits with code 0.
    output:        Combined stdout + stderr from the pytest process.
    error_type:    Best-guess exception class name (e.g. "AssertionError").
    error_summary: Last meaningful line of output (truncated to 200 chars).
    test_cases:    Per-test pass/fail list, e.g. [{"name": "test_add", "passed": True}].
    """
    passed:        bool
    output:        str
    error_type:    str
    error_summary: str
    test_cases:    list = field(default_factory=list)


def run_tests(code: str, tests: str) -> TestResult:
    """
    Write *code* and *tests* to a temporary directory and run pytest against them.

    The temp directory (and all files) is deleted automatically when the
    ``with`` block exits, regardless of whether the tests pass or fail.

    Parameters
    ----------
    code:  Python source for the solution module (``solution.py``).
    tests: Pytest test functions that import from ``solution``.

    Returns
    -------
    A populated :class:`TestResult` instance.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        code_path  = os.path.join(tmpdir, "solution.py")
        tests_path = os.path.join(tmpdir, "test_solution.py")

        with open(code_path, "w") as f:
            f.write(code)

        with open(tests_path, "w") as f:
            f.write("from solution import *\n\n")
            f.write(tests)

        result = subprocess.run(
            ["python", "-m", "pytest", tests_path, "-v", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmpdir,
        )

    output = result.stdout + result.stderr
    passed = result.returncode == 0

    return TestResult(
        passed=passed,
        output=output,
        error_type=_extract_error_type(output),
        error_summary=_extract_error_summary(output),
        test_cases=_parse_test_cases(output),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_test_cases(output: str) -> list[dict]:
    """
    Extract per-test pass/fail status from pytest ``-v`` output.

    Matches lines of the form:
        test_solution.py::test_name PASSED  [100%]
        test_solution.py::test_name FAILED  [ 60%]

    Parameters
    ----------
    output: Combined stdout + stderr from the pytest subprocess.

    Returns
    -------
    List of ``{"name": str, "passed": bool}`` dicts in execution order.
    """
    pattern = re.compile(r"::([^\s\[]+)\s+(PASSED|FAILED|ERROR)")
    cases = []
    for match in pattern.finditer(output):
        cases.append({
            "name":   match.group(1),
            "passed": match.group(2) == "PASSED",
        })
    return cases


def _extract_error_type(output: str) -> str:
    """
    Return the first recognisable exception class name found in *output*.

    Falls back to ``"AssertionError"`` when pytest's ``--tb=short`` format
    shows ``E   assert ...`` without printing the exception class name.
    Returns ``"UnknownError"`` when nothing is recognised.
    """
    known_exceptions = (
        "AssertionError", "IndexError",   "TypeError",     "ValueError",
        "KeyError",       "AttributeError", "SyntaxError", "NameError",
        "ZeroDivisionError", "RecursionError",
    )
    match = re.search("|".join(known_exceptions), output)
    if match:
        return match.group(0)

    # pytest --tb=short emits "E   assert ..." without the class name
    if re.search(r"^E\s+assert ", output, re.MULTILINE):
        return "AssertionError"

    return "UnknownError"


def _extract_error_summary(output: str) -> str:
    """
    Return the last meaningful line from *output* (up to 200 chars).

    Skips separator lines (``===`` or ``---``) and blank lines.
    """
    for line in reversed(output.strip().split("\n")):
        stripped = line.strip()
        if stripped and not stripped.startswith("=") and not stripped.startswith("-"):
            return stripped[:200]
    return "Test failed"
