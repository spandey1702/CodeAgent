import logging
from agents import CoderAgent, ReviewerAgent, DebuggerAgent, DeployerAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("code_agent.log"),
    ],
)

MAX_DEBUG_ATTEMPTS = 3

def run_pipeline():
    coder = CoderAgent()
    reviewer = ReviewerAgent()
    debugger = DebuggerAgent()
    deployer = DeployerAgent()

    print("\n--- 🤖 CodeAgent Pipeline Active ---")
    user_request = input("Enter your code requirements:\n> ")

    # ── Phase 1: Generation ───────────────────────────────────────────────────
    print("\n[1/3] Generating code...")
    current_code = coder.generate_response(user_request)
    print("\n--- Generated Code ---")
    print(current_code)

    # ── Phase 2: Review + self-healing debug loop ─────────────────────────────
    print("\n[2/3] Performing quality review...")
    for attempt in range(1, MAX_DEBUG_ATTEMPTS + 1):
        feedback = reviewer.generate_response(current_code)

        if "PASS" in feedback.upper():
            print(f"✅ Review passed (attempt {attempt})!")
            break

        print(f"❌ Review failed (attempt {attempt}/{MAX_DEBUG_ATTEMPTS}).")
        print(f"\nReviewer feedback:\n{feedback}\n")

        if attempt == MAX_DEBUG_ATTEMPTS:
            print("🛑 Max debug attempts reached. Pipeline halted.")
            print("Please refine your requirements and try again.")
            return

        print(f"🔧 Sending to Debugger (attempt {attempt})...")
        current_code = debugger.generate_response(
            f"Code:\n{current_code}\n\nBugs identified by reviewer:\n{feedback}"
        )
        print("\n--- Debugged Code ---")
        print(current_code)
        print("\n[2/3] Re-reviewing debugged code...")

    # ── Phase 3: Deploy ───────────────────────────────────────────────────────
    print("\n[3/3] Deploying to disk...")
    result = deployer.deploy(current_code, "output.py")
    print(f"\n{result}\n")


if __name__ == "__main__":
    run_pipeline()