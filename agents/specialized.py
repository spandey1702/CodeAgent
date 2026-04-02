from base import BaseAgent
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


class DeployerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "DevOps Engineer",
            "You help clean and validate code before it is saved to disk.",
        )

    def deploy(self, raw_code: str, filename: str = "app.py") -> str:
        """Strip markdown fences and write the code to the dist/ folder."""
        try:
            clean_code = raw_code.replace("```python", "").replace("```", "").strip()

            dist_path = Path("dist")
            dist_path.mkdir(exist_ok=True)

            file_path = dist_path / filename
            file_path.write_text(clean_code, encoding="utf-8")

            self.logger.info(f"Deployed to {file_path}")
            return f"✅ Successfully deployed to {file_path}"
        except Exception as e:
            self.logger.error(f"Deployment failed: {e}")
            return f"ERROR: Deployment failed — {e}"