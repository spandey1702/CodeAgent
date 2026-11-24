import logging
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .specialized import (
    CoderAgent, ReviewerAgent, DebuggerAgent, ExplainerAgent, DeployerAgent,
    SupervisorAgent, Review, syntax_error,
)

_log_file = Path.home() / "code_agent.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_log_file),
    ],
)
logger = logging.getLogger("Pipeline")

MAX_REVIEWS = 3   # so at most 2 debug rounds between them

MAX_RETRIES = 3            # run_supervised_pipeline: debug attempts specifically
MAX_SUPERVISOR_STEPS = 8   # run_supervised_pipeline: absolute backstop across all actions

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
def audit_code(code: str, requirements: str = "") -> str:
    """
    Review Python code for bugs, security issues, and bad practices.

    Args:
        code:         The Python code to review.
        requirements: Optional. What the code is supposed to do; when given,
                      the review also checks the code meets it.

    Returns:
        'PASS' if the code is acceptable, or 'FAIL' followed by a list of issues.
    """
    logger.info("audit_code called.")
    return ReviewerAgent().review(code, requirements).as_text()


@mcp.tool()
def debug_code(code: str, feedback: str, requirements: str = "") -> str:
    """
    Fix bugs in Python code based on reviewer feedback.

    Args:
        code:         The buggy Python code.
        feedback:     The reviewer's list of issues to fix.
        requirements: Optional. What the code is supposed to do.

    Returns:
        Corrected Python code as a string.
    """
    logger.info("debug_code called.")
    return DebuggerAgent().fix(code, feedback, requirements)


@mcp.tool()
def deploy_to_disk(code: str, filename: str = "generated_code.py") -> str:
    """
    Clean and save Python code to the output folder (dist/ by default).

    Args:
        code:     Python code to save (markdown fences are stripped automatically).
                  It must parse as Python.
        filename: A plain .py filename, with no folders (default: generated_code.py).

    Returns:
        Success message with the file path, or an error message.
    """
    logger.info(f"deploy_to_disk called → {filename}")
    return DeployerAgent().deploy(code, filename)


@mcp.tool()
def deploy_to_github(code: str, filename: str, repo: str, base_branch: str = "main") -> str:
    """
    Open a PR on GitHub adding/updating a file. Never pushes to base_branch
    directly — every deploy goes through a new branch + pull request.

    Args:
        code:        Python code to deploy (markdown fences stripped automatically).
                     It must parse as Python.
        filename:    A plain .py filename, with no folders.
        repo:        "owner/name" — must be listed in GITHUB_REPO_ALLOWLIST.
        base_branch: Branch to open the PR against (default: main).

    Returns:
        The opened PR's URL, or an error message.
    """
    logger.info(f"deploy_to_github called → {repo}:{filename}")
    return DeployerAgent().deploy_to_github(code, filename, repo, base_branch)


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
    return ExplainerAgent().explain(code)


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
    return CoderAgent().refactor(code, instructions)


# ── Full autonomous pipeline (killer feature) ─────────────────────────────────

def _check(code: str, requirements: str, reviewer: ReviewerAgent) -> Review:
    """Syntax first (free and certain), then the reviewer (costs an API call)."""
    error = syntax_error(code)
    if error:
        logger.info(f"Syntax check failed: {error}")
        return Review(passed=False, issues=[f"The code does not parse: {error}"])
    return reviewer.review(code, requirements)


@mcp.tool()
def run_full_pipeline(prompt: str, filename: str = "output.py") -> str:
    """
    Fully autonomous self-healing pipeline: generate → check → debug → deploy → explain.

    Generates code from a prompt, checks that it parses, then has it reviewed
    against the prompt. On failure the Debugger fixes it and it is checked
    again: up to 3 checks and 2 debug rounds. Deploys on success, then
    produces a plain-English explanation of the final code.

    Args:
        prompt:   Plain-English description of what the code should do.
        filename: A plain .py filename for the output (default: output.py).

    Returns:
        A summary of the pipeline result, including which attempt passed
        and the final file path, or an explanation of why it was halted.
    """
    logger.info(f"run_full_pipeline called → {filename}")

    coder     = CoderAgent()
    reviewer  = ReviewerAgent()
    debugger  = DebuggerAgent()
    deployer  = DeployerAgent()
    explainer = ExplainerAgent()

    # Phase 1: Generate
    logger.info("Phase 1 — Generating code...")
    current_code = coder.generate_response(prompt)

    # Phase 2: Check + self-healing loop
    for attempt in range(1, MAX_REVIEWS + 1):
        logger.info(f"Phase 2 — Check {attempt}/{MAX_REVIEWS}...")
        review = _check(current_code, prompt, reviewer)

        if review.passed:
            logger.info(f"Review passed on attempt {attempt}.")

            # Phase 3: Deploy
            logger.info("Phase 3 — Deploying...")
            deploy_result = deployer.deploy(current_code, filename)

            # Phase 4: Explain
            logger.info("Phase 4 — Generating explanation...")
            explanation = explainer.explain(current_code)

            return (
                f"✅ Pipeline complete.\n"
                f"Passed review on attempt {attempt}/{MAX_REVIEWS}.\n"
                f"{deploy_result}\n\n"
                f"--- Explanation ---\n{explanation}\n\n"
                f"--- Final Code ---\n{current_code}"
            )

        logger.warning(f"Check failed on attempt {attempt}.")

        if attempt == MAX_REVIEWS:
            return (
                f"🛑 Pipeline halted after {MAX_REVIEWS} failed checks.\n\n"
                f"Last review:\n{review.as_text()}\n\n"
                f"Last code produced:\n{current_code}"
            )

        logger.info(f"Sending to Debugger (round {attempt})...")
        current_code = debugger.fix(current_code, review.as_text(), prompt)


@mcp.tool()
def run_supervised_pipeline(
    prompt: str,
    filename: str = "output.py",
    deploy_target: str = "disk",
    repo: str = "",
) -> str:
    """
    Supervisor-driven pipeline: an LLM Supervisor decides, step by step, whether to
    review, debug, deploy, or halt — instead of run_full_pipeline's fixed loop.

    Args:
        prompt:        Plain-English description of what the code should do.
        filename:      A plain .py filename for the output (default: output.py).
        deploy_target: "disk" (default) or "github".
        repo:          Required if deploy_target == "github" — "owner/name".

    Returns:
        A summary of the pipeline result, or why the Supervisor halted it.
    """
    logger.info(f"run_supervised_pipeline called → {deploy_target}:{filename}")

    supervisor = SupervisorAgent()
    coder, reviewer, debugger, deployer, explainer = (
        CoderAgent(), ReviewerAgent(), DebuggerAgent(), DeployerAgent(), ExplainerAgent()
    )

    logger.info("Phase 1 — Generating code...")
    current_code = coder.generate_response(prompt)
    history = ["Coder produced initial code."]
    last_review: Review | None = None
    debug_count = 0

    for step in range(1, MAX_SUPERVISOR_STEPS + 1):
        if debug_count >= MAX_RETRIES:
            return f"🛑 Halted: hit the {MAX_RETRIES}-retry limit.\n\nLast code:\n{current_code}"

        decision_raw = supervisor.decide(
            prompt, current_code, history,
            last_review.as_text() if last_review else "", step, MAX_SUPERVISOR_STEPS,
        )
        lines = decision_raw.strip().splitlines()
        decision = lines[0].strip().upper() if lines else ""
        logger.info(f"Supervisor step {step}: {decision}")

        if decision == "REVIEW":
            last_review = _check(current_code, prompt, reviewer)
            history.append(f"Reviewer said: {last_review.as_text().splitlines()[0]}")

        elif decision == "DEBUG":
            debug_count += 1
            current_code = debugger.fix(
                current_code, last_review.as_text() if last_review else "", prompt
            )
            history.append(f"Debugger produced a revised version (retry {debug_count}/{MAX_RETRIES}).")

        elif decision == "DEPLOY":
            logger.info(f"Phase — Deploying to {deploy_target}...")
            if deploy_target == "github":
                if not repo:
                    return "ERROR: deploy_target='github' requires a repo argument."
                deploy_result = deployer.deploy_to_github(current_code, filename, repo)
            else:
                deploy_result = deployer.deploy(current_code, filename)

            explanation = explainer.explain(current_code)
            retry_word = "retry" if debug_count == 1 else "retries"
            return (
                f"✅ Supervised pipeline complete after {step} step(s), {debug_count} {retry_word}.\n"
                f"{deploy_result}\n\n"
                f"--- Explanation ---\n{explanation}\n\n"
                f"--- Final Code ---\n{current_code}"
            )

        elif decision == "HALT":
            return (
                f"🛑 Supervisor halted after {step} step(s).\n"
                f"Reason: {decision_raw.strip()}\n\n"
                f"Last code produced:\n{current_code}"
            )

        else:
            logger.error(f"Unrecognized supervisor decision: {decision_raw[:200]!r}")
            return (
                f"🛑 Halted: unrecognized supervisor output.\n\n"
                f"Raw response:\n{decision_raw}\n\nLast code produced:\n{current_code}"
            )

    return (
        f"🛑 Halted: hit the {MAX_SUPERVISOR_STEPS}-step safety cap without the "
        f"Supervisor choosing DEPLOY or HALT.\n\nLast code produced:\n{current_code}"
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
