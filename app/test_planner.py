"""Manual test script for LocalOps Planner."""

from __future__ import annotations

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.planner import create_plan
from app.validator import validate_plan


def main():
    if len(sys.argv) > 1:
        request = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        request = piped if piped else "why is my system slow?"
    else:
        try:
            request = input("LocalOps> ")
        except (KeyboardInterrupt, EOFError):
            print()
            return

    if not request.strip():
        print("No request provided.")
        return

    try:
        plan = create_plan(request)
        commands = validate_plan(plan)
    except (ValueError, RuntimeError) as error:
        print("\nPLAN REJECTED")
        print(error)
        raise SystemExit(1)

    print("\n─────────────────────────────────────")
    print("PLAN")
    print("─────────────────────────────────────")
    print("\nProblem:")
    print(plan["problem"])
    print("\nAssessment:")
    print(plan["assessment"])
    print(f"\nWorkflow: {plan['workflow_id']}")
    print("\nCommands:")

    for index, item in enumerate(commands, 1):
        print(f"\n{index}. $ {item['command']}")
        print(f"   What: {item['description']}")
        print(f"   Why:  {item['purpose']}")
        print(f"   Risk: {item['risk']}")
        print(f"   Read-only: {item['read_only']}")

    print("\n─────────────────────────────────────")
    print("PLAN VALIDATED")
    print("No commands have been executed.")
    print("─────────────────────────────────────")


if __name__ == "__main__":
    main()
