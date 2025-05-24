# runner.py
import os
import pathlib

import dotenv
from pocketflow import Flow

from nodes import Audit42C, LLM_PlanPatch, LoadSpec, WritePatch


def main():
    """Main entry point for the OpenAPI security enhancement agent"""
    # Load environment from project root (one level up from src/)
    project_root = pathlib.Path(__file__).parent.parent
    env_path = project_root / ".env"
    dotenv.load_dotenv(env_path)

    # Configuration
    os.environ.setdefault("MIN_SCORE", "90")
    spec_path = os.getenv("SPEC_PATH", "./sample_api.yaml")

    # Debug prints
    print(f"🔧 Debug: spec_path = {repr(spec_path)}")
    print(f"🔧 Debug: spec_path type = {type(spec_path)}")

    # Validate environment
    if not os.getenv("C42_TOKEN"):
        raise ValueError("C42_TOKEN environment variable is required")
    if not os.getenv("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY environment variable is required")

    print(f"📄 Target spec: {spec_path}")
    print(f"🎯 Target score: {os.getenv('MIN_SCORE')}")
    print("-" * 50)

    # Create nodes
    load = LoadSpec()
    audit = Audit42C()
    decide = LLM_PlanPatch()
    write = WritePatch()

    # Connect the flow
    load >> audit
    audit >> decide
    decide - "patch" >> write
    # Remove the loop back for now to fix the routing issue
    # write >> audit  # Loop back for re-audit
    # Note: The flow ends naturally when decide returns "done" action without any connected node

    # Run the flow
    flow = Flow(start=load)

    print("🚀 Starting OpenAPI Security Enhancement Agent...")

    # Create shared state dictionary
    shared_state = {
        "spec_path": spec_path,
        "min_score": int(os.getenv("MIN_SCORE", 90)),
    }
    print(f"🔧 Debug: About to call flow.run() with {repr(shared_state)}")

    try:
        result = flow.run(shared_state)
        print("\n✅ Process completed successfully!")
        return result
    except Exception as e:
        print(f"❌ Agent failed: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
