"""
agent_context.py
----------------
Holds all mutable state for one agent run and builds the prompts sent to the
LLM at each stage (generate → analyse → patch).
"""
import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Truncation limits used when storing history/analysis text
# ---------------------------------------------------------------------------
_FIX_TEXT_MAX_CHARS    = 300   # max chars saved to the memory store
_HISTORY_TEXT_MAX_CHARS = 150  # max chars kept per history entry


@dataclass
class IterationSummary:
    """
    A lightweight record of what happened in one failed iteration.

    Attributes
    ----------
    iteration:     1-based iteration index.
    error_type:    Short error class name (e.g. "AssertionError").
    fix_attempted: Brief description of the fix that was tried.
    result:        Outcome string, e.g. "failed" or "passed".
    """
    iteration:     int
    error_type:    str
    fix_attempted: str
    result:        str


@dataclass
class AgentContext:
    """
    All state needed for a single agent session.

    The context is updated after every iteration so that each LLM prompt
    carries the latest code, error output, and iteration history.
    """

    task:              str
    session_id:        str
    current_code:      Optional[str] = None
    current_tests:     Optional[str] = None
    current_error:     Optional[str] = None
    current_analysis:  Optional[str] = None
    current_memories:  list = field(default_factory=list)
    iteration_history: list[IterationSummary] = field(default_factory=list)
    max_iterations:    int = 5

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def build_generator_prompt(self) -> tuple[str, str]:
        """Return (system, user) prompts for the code-generation step."""
        system = (
            "You are an expert Python developer. "
            "When given a task, respond with ONLY two clearly labelled sections:\n"
            "## CODE\n<the Python function>\n\n## TESTS\n<pytest test functions>\n"
            "No explanation. No markdown fences. Just the two sections."
        )

        user = f"Task: {self.task}"
        if self.iteration_history:
            last = self.iteration_history[-1]
            user += (
                f"\n\nPrevious attempt failed.\n"
                f"Error type: {last.error_type}\n"
                f"What was tried: {last.fix_attempted}\n"
                f"Fix it."
            )
        return system, user

    def build_analyzer_prompt(self, relevant_memories: list) -> tuple[str, str]:
        """
        Return (system, user) prompts for the error-analysis step.

        The system prompt instructs the LLM to respond with structured JSON
        so the UI can render the three labeled critic rows directly.

        Parameters
        ----------
        relevant_memories: Retrieved memory entries similar to the current error.
        """
        system = (
            "You are a debugging expert. Analyse the test failure and identify the root cause. "
            "Respond with valid JSON only — no prose, no markdown, no code fences. "
            "Use this exact schema:\n"
            '{"error_class": "<short snake_case label, e.g. off_by_one>",'
            ' "root_cause": "<one concise sentence describing the root cause>",'
            ' "fix_hint": "<one concise sentence describing how to fix it>"}'
        )

        memory_text = ""
        if relevant_memories:
            memory_text = "\n\nSimilar past mistakes from memory:\n"
            for m in relevant_memories:
                memory_text += f"- {m['error_text']} → fixed by: {m['fix_attempts'][-1]['fix_text']}\n"

        user = (
            f"Task: {self.task}\n\n"
            f"Code that failed:\n{self.current_code}\n\n"
            f"Test output:\n{self.current_error}"
            f"{memory_text}"
        )
        return system, user

    def build_patcher_prompt(self, relevant_memories: list) -> tuple[str, str]:
        """
        Return (system, user) prompts for the code-patching step.

        Parameters
        ----------
        relevant_memories: Retrieved memory entries similar to the current error.
        """
        system = (
            "You are an expert Python developer fixing buggy code. "
            "Respond with ONLY two clearly labelled sections:\n"
            "## CODE\n<fixed Python function>\n\n## TESTS\n<pytest test functions>\n"
            "No explanation. No markdown fences."
        )

        history_text = ""
        if self.iteration_history:
            history_text = "\n\nIteration history:\n"
            for h in self.iteration_history:
                history_text += f"- Iteration {h.iteration}: tried '{h.fix_attempted}' → {h.result}\n"

        memory_text = ""
        if relevant_memories:
            memory_text = "\n\nKnown fixes for similar mistakes:\n"
            for m in relevant_memories:
                memory_text += f"- {m['error_text']} → {m['fix_attempts'][-1]['fix_text']}\n"

        user = (
            f"Task: {self.task}\n\n"
            f"Broken code:\n{self.current_code}\n\n"
            f"Root cause:\n{self.current_analysis}"
            f"{history_text}"
            f"{memory_text}"
        )
        return system, user

    # ------------------------------------------------------------------
    # State mutators
    # ------------------------------------------------------------------

    def update_history(self, error_type: str, fix_attempted: str, result: str) -> None:
        """Append a new IterationSummary to the history list."""
        self.iteration_history.append(IterationSummary(
            iteration=len(self.iteration_history) + 1,
            error_type=error_type,
            fix_attempted=fix_attempted,
            result=result,
        ))

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def parse_llm_response(self, response: str) -> tuple[str, str]:
        """
        Extract ``(code, tests)`` from a raw LLM response.

        Handles variations in heading level (### CODE, ## CODE, etc.) and
        strips any surrounding markdown code fences.
        """
        code, tests = "", ""

        # Normalise section headers so splitting is always on "## CODE" / "## TESTS"
        response = re.sub(r'^#{1,4}\s*CODE\b',  '## CODE',  response, flags=re.MULTILINE)
        response = re.sub(r'^#{1,4}\s*TESTS\b', '## TESTS', response, flags=re.MULTILINE)

        if "## CODE" in response and "## TESTS" in response:
            parts = response.split("## TESTS")
            code  = parts[0].replace("## CODE", "").strip()
            tests = parts[1].strip()

        def strip_fences(text: str) -> str:
            """Remove opening and closing markdown code fences."""
            # Remove opening fence line  (```python, ```py, ```, etc.)
            text = re.sub(r'^```[a-zA-Z]*\n?', '', text.strip(), flags=re.MULTILINE)
            # Remove closing fence
            text = re.sub(r'\n?```\s*$', '', text.strip(), flags=re.MULTILINE)
            # Remove any remaining standalone fence lines
            text = re.sub(r'^```[a-zA-Z]*$', '', text, flags=re.MULTILINE)
            return text.strip()

        return strip_fences(code), strip_fences(tests)
