#!/usr/bin/env python3
"""
OpenAPI Security Enhancement Agent

An agentic AI system that automatically improves OpenAPI specifications
by iteratively running 42crunch security audits and applying AI-generated fixes.

Supports both direct OpenAPI files and FastAPI projects.
"""

import os
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.runner import main as run_agent


def main():
    print("🤖 OpenAPI Security Enhancement Agent")
    print("=====================================")

    # Check if .env file exists
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found!")
        print("📝 Create a .env file with the following variables:")
        print()
        print("# Required")
        print("C42_TOKEN=your_42crunch_token_here")
        print("GROQ_API_KEY=your_groq_api_key_here")
        print()
        print("# Target (choose one)")
        print("SPEC_PATH=/path/to/your/fastapi-project    # For FastAPI projects")
        print("# SPEC_PATH=./openapi-spec.yaml           # For direct OpenAPI files")
        print()
        print("# Optional")
        print("MIN_SCORE=90")
        print("FASTAPI_HOST=127.0.0.1")
        print("FASTAPI_PORT=8000")
        print()
        print("💡 Get a free Groq API key from: https://console.groq.com")
        print("💡 Get 42crunch token from: https://42crunch.com")
        return 1

    # Show what will be processed
    from dotenv import load_dotenv

    load_dotenv()

    spec_path = os.getenv("SPEC_PATH")
    if not spec_path:
        print("❌ SPEC_PATH not set in .env file!")
        print("Set it to either:")
        print("  - A FastAPI project directory")
        print("  - A direct OpenAPI file (.yaml/.json)")
        return 1

    target_path = Path(spec_path)
    if target_path.is_dir():
        print(f"🚀 Will process FastAPI project: {spec_path}")
    elif target_path.is_file():
        print(f"📄 Will process OpenAPI file: {spec_path}")
    else:
        print(f"❌ Path not found: {spec_path}")
        return 1

    try:
        result = run_agent()

        # Show results based on type
        if target_path.is_dir():
            print("\n🎉 FastAPI project analysis complete!")
            print("📁 Check your project directory for:")
            print("   📋 security_improvements.md - Implementation guide")
            print("   📄 openapi_improved.yaml - Enhanced OpenAPI spec")
        else:
            print("\n🎉 OpenAPI file enhancement complete!")
            print("📄 Improved spec saved with backup")

        print(result)

        return 0
    except Exception as e:
        print(f"❌ Agent failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
