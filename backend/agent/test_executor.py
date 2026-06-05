import subprocess
import tempfile
import os
import re
from dataclasses import dataclass

@dataclass
class TestResult:
    passed: bool
    output: str
    error_type: str
    error_summary: str

def run_tests(code: str, tests: str) -> TestResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        code_path  = os.path.join(tmpdir, "solution.py")
        tests_path = os.path.join(tmpdir, "test_solution.py")

        with open(code_path,  "w") as f: f.write(code)
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
    )

def _extract_error_type(output: str) -> str:
    match = re.search(r'(AssertionError|IndexError|TypeError|ValueError|'
                      r'KeyError|AttributeError|SyntaxError|NameError|'
                      r'ZeroDivisionError|RecursionError)', output)
    if match:
        return match.group(1)
    # pytest --tb=short shows assertion failures as "E   assert ..." without
    # printing the exception class name explicitly — detect that pattern here
    if re.search(r'^E\s+assert ', output, re.MULTILINE):
        return "AssertionError"
    return "UnknownError"

def _extract_error_summary(output: str) -> str:
    lines = output.strip().split("\n")
    for line in reversed(lines):
        if line.strip() and not line.startswith("=") and not line.startswith("-"):
            return line.strip()[:200]
    return "Test failed"
