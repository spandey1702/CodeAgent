"""
Example: run the full pipeline to generate a FastAPI endpoint.

Run from the repo root with ANTHROPIC_API_KEY set (makes several API calls):
    python examples/fastapi_endpoint.py

In Claude Desktop, Cursor or Windsurf, ask: "Use run_full_pipeline to build ..."
followed by the same requirements.
"""
from codeagent_mcp.plugin_server import run_full_pipeline

REQUIREMENTS = """
Build a FastAPI endpoint that:
- Accepts a POST request at /users with a JSON body containing name (str) and email (str)
- Validates that email contains '@'
- Returns {"status": "created", "user": {"name": ..., "email": ...}} on success
- Returns a 422 with a clear message on validation failure
"""

if __name__ == "__main__":
    print(run_full_pipeline(REQUIREMENTS, "user_endpoint.py"))
