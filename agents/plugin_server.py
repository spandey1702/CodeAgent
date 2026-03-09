from mcp.server.fastmcp import FastMCP
from specialized import CoderAgent, ReviewerAgent, DeployerAgent
import sys
import logging

# Initialize FastMCP
mcp = FastMCP("SDLC-Automation-Agent")

@mcp.tool()
def develop_feature(prompt: str) -> str:
    """Skill: Generates code based on requirements."""
    return CoderAgent().generate_response(prompt)

@mcp.tool()
def audit_code(code: str) -> str:
    """Skill: Reviews code for bugs (Returns PASS/FAIL)."""
    return ReviewerAgent().generate_response(code)

@mcp.tool()
def deploy_to_disk(code: str, name: str = "generated_code.py") -> str:
    """Skill: Cleans and saves the final code to the 'dist' folder."""
    return DeployerAgent().deploy(code, name)

# 3. The CLI Pipeline

def run_interactive_pipeline():
    coder = CoderAgent()
    reviewer = ReviewerAgent()
    deployer = DeployerAgent()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger("Pipeline")

    print("\n--- CodeAgent Pipeline Active ---")
    user_request = input("Enter your code requirements: \n> ")

    try:
        logger.info("Generating code...")
        print("\n[1/3] Generating Code...")
        current_code = coder.generate_response(user_request)

        logger.info("Reviewing generated code...")
        print("[2/3] Performing Quality Review...")
        feedback = reviewer.generate_response(current_code)
        
        if "PASS" in feedback.upper():
            logger.info("Code review passed.")
            print("Review Passed!")
            print("[3/3] Deploying to Disk...")
            result = deployer.deploy(current_code, "output.py")
            logger.info("Deployment successful.")
            print(f"\n{result}\n")
        else:
            logger.warning("Code review failed.")
            print(f"Review Failed.\n\nFeedback:\n{feedback}")
    except Exception as e:
        logger.error(f"Pipeline encountered an error: {e}")
        print(f"ERROR: {e}")