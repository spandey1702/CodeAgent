from specialized import CoderAgent, ReviewerAgent, DebuggerAgent, DeployerAgent

def run_pipeline():
    # Initialize  agents
    coder = CoderAgent()
    reviewer = ReviewerAgent()
    deployer = DeployerAgent()

    print("--- 🤖 CodeAgent Pipeline Active ---")
    user_request = input("Enter your code requirements: \n> ")

    # PHASE 1: GENERATION
    print("\n[1/3] Generating Code...")
    current_code = coder.generate_response(user_request)

    # PHASE 2: QUALITY AUDIT
    print("[2/3] Performing Quality Review...")
    feedback = reviewer.generate_response(current_code)
    
    # Check for the 'PASS' keyword to determine if the code is acceptable
    if "PASS" in feedback.upper():
        print("Review Passed!")
        
        # PHASE 3: DEPLOYMENT
        print("[3/3] Deploying to Disk...")
        result = deployer.deploy(current_code)
        print(f"\n{result}\n")
    else:
        print("Review Failed.")
        print(f"\nFeedback from Reviewer:\n{feedback}")
        print("\nPipeline halted. Please refine requirements and try again.")

if __name__ == "__main__":
    run_pipeline()