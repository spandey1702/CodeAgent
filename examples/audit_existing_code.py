"""
Example: audit code you already wrote.

Run from the repo root with ANTHROPIC_API_KEY set (makes one API call):
    python examples/audit_existing_code.py
"""
from codeagent_mcp import ReviewerAgent

CODE_TO_REVIEW = """
import sqlite3

def get_user(username):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
    return cursor.fetchone()
"""

REQUIREMENTS = "Look up a user by username in app.db and return their row."

if __name__ == "__main__":
    # Expected: FAIL, with the SQL injection flagged
    print(ReviewerAgent().review(CODE_TO_REVIEW, REQUIREMENTS).as_text())
