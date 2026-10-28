from __future__ import annotations

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.planner import create_plan
from app.validator import validate_plan
from app.executor import execute_plan
from app.analyzer import analyze_results


def main():
    user_request = "Why is my system slow?"

    print("LocalOps Analyzer Test")
    print("=" * 40)

    # --------------------------------------------------
    # STEP 1 — Create plan
    # --------------------------------------------------

    print("\n[1] Creating troubleshooting plan...")

    plan = create_plan(user_request)

    print("PLAN CREATED")

    # --------------------------------------------------
    # STEP 2 — Validate plan
    # --------------------------------------------------

    print("\n[2] Validating plan...")

    validated_commands = validate_plan(plan)

    print("PLAN VALIDATED")

    for command in validated_commands:
        print(f"  ${command['command']}")

    # --------------------------------------------------
    # STEP 3 — Execute validated plan
    # --------------------------------------------------

    print("\n[3] Executing validated commands...")

    results = execute_plan(
        validated_commands,
        confirm=True,
    )

    for index, result in enumerate(results, 1):

        command = result.get("command", "unknown")

        print(f"\n[{index}] ${command}")

        # Safely read result fields
        return_code = result.get("return_code")
        success = result.get("success")
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")

        print(f"Exit code: {return_code}")
        print(f"Success: {success}")

        if stdout:
            print("Output:")
            print(stdout)

        if stderr:
            print("STDERR:")
            print(stderr)

    # --------------------------------------------------
    # STEP 4 — Analyze results
    # --------------------------------------------------

    print("\n" + "=" * 40)
    print("[4] Sending results to SLM Analyzer...")
    print("=" * 40)

    analysis = analyze_results(
        user_request,
        results,
    )

    # --------------------------------------------------
    # STEP 5 — Display diagnosis
    # --------------------------------------------------

    print("\nDIAGNOSIS")
    print("=" * 40)

    for item in analysis["diagnosis"]:

        print(
            f"\nProblem: "
            f"{item.get('problem', 'Unknown')}"
        )

        print(
            f"Severity: "
            f"{item.get('severity', 'unknown')}"
        )

        print(
            f"Evidence: "
            f"{item.get('evidence', 'No evidence provided')}"
        )

        print(
            f"Confidence: "
            f"{item.get('confidence', 'unknown')}"
        )

    print("\nSUMMARY")
    print("=" * 40)
    print(analysis["summary"])

    print("\nNEXT ACTIONS")
    print("=" * 40)

    if not analysis["next_actions"]:
        print("No additional diagnostic action recommended.")

    else:
        for action in analysis["next_actions"]:

            print(
                f"\nCommand ID: "
                f"{action.get('command_id')}"
            )

            print(
                f"Options: "
                f"{action.get('options', [])}"
            )

            print(
                f"Reason: "
                f"{action.get('reason', '')}"
            )

    print("\nEnough evidence:")
    print(analysis["enough_evidence"])


if __name__ == "__main__":
    main()
