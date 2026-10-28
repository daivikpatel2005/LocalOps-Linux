"""Manual test script for LocalOps Executor."""

from __future__ import annotations

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.executor import execute_plan
from app.validator import validate_plan


def main():
    plan = {
        "problem": "Test system diagnostics",
        "assessment": "Testing safe read-only diagnostic commands.",
        "workflow_id": "system_slow",
        "plan": [
            {
                "command_id": "uptime",
                "options": [],
                "purpose": "Check system load",
            },
            {
                "command_id": "free",
                "options": ["-h"],
                "purpose": "Check RAM and swap usage",
            },
            {
                "command_id": "df",
                "options": ["-h"],
                "purpose": "Check filesystem capacity",
            },
            {
                "command_id": "ps",
                "options": ["aux"],
                "purpose": "Inspect running processes",
            },
        ],
    }

    print()
    print("─────────────────────────────────────")
    print("LocalOps Executor Test")
    print("─────────────────────────────────────")

    try:
        validated_commands = validate_plan(plan)

        print()
        print("PLAN VALIDATED")
        print("Executing validated commands...")
        print()

        results = execute_plan(
            validated_commands,
            confirm=True,
        )

        for index, result in enumerate(results, 1):
            print(f"[{index}/{len(results)}] ${result['command']}")
            print(f"Exit code: {result['return_code']}")
            print(f"Success: {result['success']}")

            if result["stdout"]:
                print("\nOutput:")
                # Show first few lines for readability
                lines = result["stdout"].splitlines()
                preview = "\n".join(lines[:5])
                if len(lines) > 5:
                    preview += f"\n... ({len(lines) - 5} more lines)"
                print(preview)

            if result["stderr"]:
                print("\nError:")
                print(result["stderr"])

            print()

    except Exception as error:
        print()
        print("EXECUTION FAILED")
        print(error)

    print("─────────────────────────────────────")
    print("Executor test complete")
    print("─────────────────────────────────────")


if __name__ == "__main__":
    main()
