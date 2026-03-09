from base import BaseAgent
from pathlib import Path

class CoderAgent(BaseAgent):
    def __init__(self):
        super().__init__("Developer", "Write clean, modular code based on requirements.")

class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Reviewer", 
            "Review the code. If it is good, start your response with 'PASS'. "
            "If it has issues, start with 'FAIL' and list the bugs.")

class DebuggerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Bug Hunter", "Fix the bugs identified by the Reviewer and return the full corrected code.")

class DeployerAgent(BaseAgent):
    def __init__(self):
        super().__init__("DevOps Engineer", "Clean the code and save it to disk.")

    def deploy(self, raw_code, filename="app.py"):
        try:
            clean_code = raw_code.replace("```python", "").replace("```", "").strip()
            
            # Create the dist directory if it doesn't exist
            dist_path = Path("dist")
            dist_path.mkdir(exist_ok=True)
            
            file_path = dist_path / filename
            with open(file_path, "w") as f:
                f.write(clean_code)
            
            self.logger.info(f"Deployed to {file_path}")
            return f"Successfully deployed to {file_path}"
        except Exception as e:
            self.logger.error(f"Deployment failed: {e}")
            return f"ERROR: Deployment failed due to {e}"