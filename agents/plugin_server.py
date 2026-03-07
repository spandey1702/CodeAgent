from mcp.server.fastmcp import FastMCP
from specialized import CoderAgent, ReviewerAgent, DeployerAgent

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
def deploy_to_disk(code: str, name: str) -> str:
    """Skill: Cleans and saves the final code to the 'dist' folder."""
    return DeployerAgent().deploy(code, name)

if __name__ == "__main__":
    mcp.run()