import logging
import sys
from mcp.server.fastmcp import FastMCP
from specialized import CoderAgent, ReviewerAgent, DebuggerAgent, ExplainerAgent, DeployerAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("code_agent.log"),
    ],
)
logger = logging.getLogger("Pipeline")

MAX_DEBUG_ATTEMPTS = 3

# ── MCP server ────────────────────────────────────────────────────────────────
mcp = FastMCP("codeagent-mcp")


# ── Individual tools (granular control) ──────────────────────────────────────

@mcp.tool()
def develop_feature(prompt: str) -> str:
    """
    Generate Python code from a plain-English description.

    Args:
        prompt: A description of what the code should do.

    Returns:
        Raw Python code as a string.
    """
    logger.info("develop_feature called.")
    return CoderAgent().generate_response(prompt)


@mcp.tool()
def audit_code(code: str) -> str:
    """
    Review Python code for bugs, security issues, and bad practices.

    Args:
        code: The Python code to review.

    Returns:
        Starts with 'PASS' if code is acceptable, or 'FAIL' followed by
        a detailed list of issues.
    """
    logger.info("audit_code called.")
    return ReviewerAgent().generate_response(code)


@mcp.tool()
def debug_code(code: str, feedback: str) -> str:
    """
    Fix bugs in Python code based on reviewer feedback.

    Args:
        code:     The buggy Python code.
        feedback: The reviewer's list of issues to fix.

    Returns:
        Corrected Python code as a string.
    """
    logger.info("debug_code called.")
    return DebuggerAgent().generate_response(
        f"Code:\n{code}\n\nBugs identified by reviewer:\n{feedback}"
    )


@mcp.tool()
def deploy_to_disk(code: str, filename: str = "generated_code.py") -> str:
    """
    Clean and save Python code to the dist/ folder.

    Args:
        code:     Python code to save (markdown fences are stripped automatically).
        filename: Output filename inside dist/ (default: generated_code.py).

    Returns:
        Success message with the file path, or an error message.
    """
    logger.info(f"deploy_to_disk called → dist/{filename}")
    return DeployerAgent().deploy(code, filename)


@mcp.tool()
def explain_code(code: str) -> str:
    """
    Produce a clear plain-English explanation of what a piece of code does.

    Args:
        code: The Python code to explain.

    Returns:
        A developer-friendly explanation of the code's purpose, logic, and structure.
    """
    logger.info("explain_code called.")
    return ExplainerAgent().generate_response(code)


@mcp.tool()
def refactor_code(code: str, instructions: str) -> str:
    """
    Refactor existing code according to specific instructions.

    Args:
        code:         The Python code to refactor.
        instructions: What to change (e.g. 'make it async', 'split into functions',
                      'add type hints', 'optimise for performance').

    Returns:
        Refactored Python code as a string.
    """
    logger.info("refactor_code called.")
    return CoderAgent().generate_response(
        f"Refactor the following Python code. Instructions: {instructions}\n\n"
        f"Code:\n{code}\n\n"
        f"Return only the refactored code with no extra explanation."
    )


# ── Full autonomous pipeline (killer feature) ─────────────────────────────────

@mcp.tool()
def run_full_pipeline(prompt: str, filename: str = "output.py") -> str:
    """
    Fully autonomous self-healing pipeline: generate → review → debug → deploy.

    Generates code from a prompt, reviews it, and if it fails automatically
    sends it to the Debugger and re-reviews. Repeats up to 3 times. Deploys
    to dist/ on success.

    Args:
        prompt:   Plain-English description of what the code should do.
        filename: Output filename inside dist/ (default: output.py).

    Returns:
        A summary of the pipeline result, including which attempt passed
        and the final file path, or an explanation of why it was halted.
    """
    logger.info(f"run_full_pipeline called → dist/{filename}")

    coder    = CoderAgent()
    reviewer = ReviewerAgent()
    debugger = DebuggerAgent()
    deployer = DeployerAgent()

    # Phase 1: Generate
    logger.info("Phase 1 — Generating code...")
    current_code = coder.generate_response(prompt)

    # Phase 2: Review + self-healing loop
    for attempt in range(1, MAX_DEBUG_ATTEMPTS + 1):
        logger.info(f"Phase 2 — Review attempt {attempt}/{MAX_DEBUG_ATTEMPTS}...")
        feedback = reviewer.generate_response(current_code)

        if "PASS" in feedback.upper():
            logger.info(f"Review passed on attempt {attempt}.")

            # Phase 3: Deploy
            logger.info("Phase 3 — Deploying...")
            deploy_result = deployer.deploy(current_code, filename)

            return (
                f"✅ Pipeline complete.\n"
                f"Passed review on attempt {attempt}/{MAX_DEBUG_ATTEMPTS}.\n"
                f"{deploy_result}\n\n"
                f"--- Final Code ---\n{current_code}"
            )

        logger.warning(f"Review failed on attempt {attempt}.")

        if attempt == MAX_DEBUG_ATTEMPTS:
            return (
                f"🛑 Pipeline halted after {MAX_DEBUG_ATTEMPTS} failed review attempts.\n\n"
                f"Last reviewer feedback:\n{feedback}\n\n"
                f"Last code produced:\n{current_code}"
            )

        logger.info(f"Sending to Debugger (attempt {attempt})...")
        current_code = debugger.generate_response(
            f"Code:\n{current_code}\n\nBugs identified by reviewer:\n{feedback}"
        )


# ── CLI + package entrypoint ──────────────────────────────────────────────────

def run_interactive_pipeline():
    """Interactive terminal pipeline — mirrors run_full_pipeline with print output."""
    print("\n--- 🤖 CodeAgent Pipeline Active ---")
    user_request = input("Enter your code requirements:\n> ")
    filename = input("Output filename (default: output.py):\n> ").strip() or "output.py"

    result = run_full_pipeline(user_request, filename)
    print(f"\n{result}")


def main():
    """Packaged entrypoint — called by the `codeagent` CLI command after pip install."""
    if "--cli" in sys.argv:
        run_interactive_pipeline()
    else:
        mcp.run()


if __name__ == "__main__":
    main()