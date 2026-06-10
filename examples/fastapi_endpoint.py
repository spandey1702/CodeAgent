"""
Example: use run_full_pipeline to generate a FastAPI endpoint.

Run this from within Claude Desktop, Cursor, or Windsurf after
installing the MCP server. The prompt below is what you'd type
in the chat — this file is for documentation purposes.
"""

EXAMPLE_PROMPT = """
Use run_full_pipeline to build a FastAPI endpoint that:
- Accepts a POST request at /users with a JSON body containing name (str) and email (str)
- Validates that email contains '@'
- Returns {"status": "created", "user": {"name": ..., "email": ...}} on success
- Returns a 422 with a clear message on validation failure
Save it as user_endpoint.py
"""
