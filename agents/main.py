from agents.specialized import CoderAgent, ReviewerAgent, DebuggerAgent, DeployerAgent

def run_pipeline():
    coder = CoderAgent()
    reviewer = ReviewerAgent()
    debugger = DebuggerAgent()
    deployer = DeployerAgent()

    print("--- 🤖 CodeAgent Pipeline Active ---")
    user_request = input("Enter your code requirements: \n> ")

    # PHASE 1: INITIAL CODE
    print("\n[1/4] Coding...")
    current_code = coder.generate_response(user_request)

    # PHASE 2 & 3: REVIEW & DEBUG LOOP
    max_retries = 3
    attempt = 0
    passed_review = False

    while attempt < max_retries and not passed_review:
        attempt += 1
        print(f"[Loop] Reviewing Attempt {attempt}...")
        
        feedback = reviewer.generate_response(current_code)
        
        if "PASS" in feedback.upper():
            print("Review Passed!")
            passed_review = True
        else:
            print(f"Review Failed. Debugging...")
            current_code = debugger.generate_response(
                f"CODE: {current_code}\n\nFEEDBACK: {feedback}"
            )

    # PHASE 4: FILE I/O DEPLOYMENT
    if passed_review:
        print("[4/4] Deploying...")
        result = deployer.deploy(current_code)
        print(f"\n{result}\n")
    else:
        print("\n🚨 Pipeline failed to produce secure/working code after 3 attempts.")

if __name__ == "__main__":
    run_pipeline()