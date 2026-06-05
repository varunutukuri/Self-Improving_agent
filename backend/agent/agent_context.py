from dataclasses import dataclass, field
from typing import Optional

@dataclass
class IterationSummary:
    iteration: int
    error_type: str
    fix_attempted: str
    result: str

@dataclass
class AgentContext:
    task: str
    session_id: str
    current_code: Optional[str] = None
    current_tests: Optional[str] = None
    current_error: Optional[str] = None
    current_analysis: Optional[str] = None
    iteration_history: list[IterationSummary] = field(default_factory=list)
    max_iterations: int = 5

    def build_generator_prompt(self) -> tuple[str, str]:
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
        system = (
            "You are a debugging expert. Analyse the test failure and identify the root cause. "
            "Be concise — one paragraph maximum."
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

    def update_history(self, error_type: str, fix_attempted: str, result: str):
        self.iteration_history.append(IterationSummary(
            iteration=len(self.iteration_history) + 1,
            error_type=error_type,
            fix_attempted=fix_attempted,
            result=result,
        ))

    def parse_llm_response(self, response: str) -> tuple[str, str]:
        code, tests = "", ""
        if "## CODE" in response and "## TESTS" in response:
            parts = response.split("## TESTS")
            code = parts[0].replace("## CODE", "").strip()
            tests = parts[1].strip()
        return code, tests
