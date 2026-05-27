import re
from .base import BaseAgent
from pathlib import Path


class CoderAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "Developer",
            "Write clean, modular, well-commented Python code based on the requirements. "
            "Return only the raw code with no extra explanation outside of inline comments.",
        )


class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "Code Reviewer",
            "Review the provided code for bugs, security issues, and bad practices. "
            "If the code is acceptable, start your response with 'PASS'. "
            "If it has issues, start your response with 'FAIL' and list every problem clearly.",
        )


class DebuggerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "Bug Hunter",
            "You receive code and a list of bugs. "
            "Fix every bug identified and return the complete corrected code only, "
            "with no additional explanation outside of inline comments.",
        )


class ExplainerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "Code Explainer",
            "You explain Python code to developers. "
            "Describe what the code does, how it works, and what each major section is "
            "responsible for. Write in clear plain English. Do NOT review for bugs or "
            "suggest changes — your only job is to explain.",
        )


class DeployerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "DevOps Engineer",
            "You help clean and validate code before it is saved to disk.",
        )

    @staticmethod
    def _extract_code(raw: str) -> str:
        """
        Extract the first Python code block from a markdown-formatted response.

        Strategy:
        1. If the response contains a fenced code block (```python … ``` or
           ``` … ```), return only that block's content — discarding any
           surrounding prose.
        2. Otherwise return the raw text stripped of whitespace, assuming the
           model returned plain code without fences.
        """
        # Match ```python … ``` or ``` … ``` (non-greedy, DOTALL)
        pattern = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
        matches = pattern.findall(raw)
        if matches:
            return matches[0].strip()
        # Fallback: strip any stray backtick fences and return as-is
        return raw.replace("```python", "").replace("```", "").strip()

    def deploy(self, raw_code: str, filename: str = "app.py") -> str:
        """Strip markdown fences / surrounding prose, then write to dist/."""
        try:
            clean_code = self._extract_code(raw_code)

            dist_path = Path("dist")
            dist_path.mkdir(exist_ok=True)

            file_path = dist_path / filename
            file_path.write_text(clean_code, encoding="utf-8")

            self.logger.info(f"Deployed to {file_path}")
            return f"✅ Successfully deployed to {file_path}"
        except Exception as e:
            self.logger.error(f"Deployment failed: {e}")
            return f"ERROR: Deployment failed — {e}"