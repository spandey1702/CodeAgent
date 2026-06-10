"""
Example: audit a file you already wrote.

Paste the code as a string and call audit_code.
The reviewer returns PASS (with notes) or FAIL (with specific issues).
"""

CODE_TO_REVIEW = """
import sqlite3

def get_user(username):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
    return cursor.fetchone()
"""

# Expected result: FAIL — SQL injection vulnerability flagged
