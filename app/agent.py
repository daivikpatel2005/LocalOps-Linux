"""Agent module for LocalOps.

Runs the troubleshooting pipeline: planning, validation, confirmation, execution,
and diagnosis.
"""

from __future__ import annotations

from typing import Any

from .analyzer import analyze_results
from .confirm import confirm_plan
from .executor import execute_plan
from .knowledge import get_workflow
from .planner import build_deterministic_plan, create_plan
from .validator import validate_plan


def print_plan(plan: dict[str, Any], validated_commands: list[dict[str, Any]]) -> None:
    print("\n─────────────────────────────────────")
    print("PLAN")
    print("─────────────────────────────────────")
    print("\nProblem:")
    print(plan.get("problem", ""))

    print("\nAssessment:")
    print(plan.get("assessment", ""))

    if plan.get("workflow_id"):
        print(f"\nWorkflow: {plan['workflow_id']}")

    print("\nCommands:")
    for index, item in enumerate(validated_commands, 1):
        print(f"\n{index}. $ {item['command']}")
        print(f"   What: {item.get('description', '')}")
        print(f"   Why:  {item.get('purpose', '')}")
        print(f"   Risk: {item.get('risk', 'low')}")
        print(f"   Read-only: {item.get('read_only', True)}")
    print("\n─────────────────────────────────────")


def run_agent(user_request: str) -> None:
    print("\nLocalOps is analyzing problem...")

    try:
        plan = create_plan(user_request)
    except Exception as error:
        print(f"\nPlanning error: {error}")
        return

    try:
        validated_commands = validate_plan(plan)
    except Exception as error:
        wf_id = plan.get("workflow_id") if isinstance(plan, dict) else None
        wf = get_workflow(wf_id) if wf_id else None
        if wf_id and wf:
            print(f"\n[Notice] Model suggested an unapproved option ({error}).")
            print(f"Falling back to verified diagnostic plan for workflow '{wf_id}'.")
            plan = build_deterministic_plan(user_request, wf_id, wf)
            validated_commands = validate_plan(plan)
        else:
            print(f"\nValidation rejected: {error}")
            return

    print_plan(plan, validated_commands)

    approved = confirm_plan(validated_commands)
    if not approved:
        print("\nExecution cancelled by user.")
        return

    print("\nExecuting validated commands...")
    try:
        results = execute_plan(validated_commands, confirm=True)
    except Exception as error:
        print(f"\nExecution error: {error}")
        return

    if not results:
        print("No execution results returned.")
        return

    print("\n─────────────────────────────────────")
    print("ANALYZING RESULTS")
    print("─────────────────────────────────────")

    analysis = analyze_results(user_request, results)

    print("\nDiagnosis:")
    for item in analysis.get("diagnosis", []):
        print(f"\n- Problem: {item.get('problem', 'Unknown')}")
        print(f"  Severity: {item.get('severity', 'unknown')}")
        print(f"  Confidence: {item.get('confidence', 'unknown')}")
        if item.get("cause"):
            print(f"  Cause / What is Happening: {item.get('cause')}")
        if item.get("evidence"):
            print(f"  Evidence: {item.get('evidence')}")
        fixes = item.get("fix_recommendations", [])
        if fixes:
            print("  How to Fix / Recommended Steps:")
            for f_idx, step in enumerate(fixes, 1):
                print(f"    {f_idx}. {step}")

    print(f"\nSummary: {analysis.get('summary', '')}")
    print("─────────────────────────────────────")
