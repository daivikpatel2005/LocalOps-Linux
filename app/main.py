"""LocalOps — Offline Linux Troubleshooting Agent CLI entry point.

Coordinates user input, planning, validation, confirmation, execution,
and diagnostic reporting.
"""

from __future__ import annotations

import sys
from typing import Any

from .analyzer import analyze_results
from .confirm import confirm_plan
from .executor import execute_plan
from .knowledge import get_workflow
from .llm import check_ollama
from .planner import build_deterministic_plan, create_plan
from .validator import validate_plan


def print_plan(commands: list[dict[str, Any]]) -> None:
    print()
    print("TROUBLESHOOTING PLAN")
    print("=" * 60)

    for index, command in enumerate(commands, 1):
        print(f"{index}. ${command['command']}")
        purpose = command.get("purpose", "")
        if purpose:
            print(f"   Purpose: {purpose}")
        risk = command.get("risk", "low")
        print(f"   Risk:    {risk} (read-only: True, sudo: False)")


def print_results(results: list[dict[str, Any]]) -> None:
    print()
    print("COMMAND RESULTS")
    print("=" * 60)

    for index, result in enumerate(results, 1):
        print(f"\n[{index}] ${result['command']}")
        print(f"Exit code: {result['return_code']}")
        print(f"Success:   {result['success']}")

        if result.get("timed_out"):
            print("Status:    Timed out")

        stdout = result.get("stdout")
        if stdout:
            print("\nOutput:")
            print(stdout)

        stderr = result.get("stderr")
        if stderr:
            print("\nError output:")
            print(stderr)


def print_analysis(analysis: dict[str, Any]) -> None:
    print()
    print("LOCALOPS DIAGNOSIS")
    print("=" * 60)

    diagnosis_items = analysis.get("diagnosis", [])
    if diagnosis_items:
        for index, item in enumerate(diagnosis_items, 1):
            if len(diagnosis_items) > 1:
                print(f"\n[{index}] {item.get('problem', 'Unknown')}")
            else:
                print(f"\nProblem:    {item.get('problem', 'Unknown')}")
            print(f"Severity:   {item.get('severity', 'unknown')}")
            print(f"Confidence: {item.get('confidence', 'unknown')}")

            cause = item.get("cause")
            if cause:
                print(f"\nWhat is Happening & Likely Cause:\n{cause}")

            evidence = item.get("evidence")
            if evidence:
                print(f"\nEvidence:\n{evidence}")

            fixes = item.get("fix_recommendations", [])
            if fixes:
                print("\nHow to Fix / Recommended Steps:")
                for fix_idx, step in enumerate(fixes, 1):
                    print(f"  {fix_idx}. {step}")
    else:
        print("\nNo specific issues diagnosed.")

    top_fixes = analysis.get("fix_recommendations", [])
    if not diagnosis_items and top_fixes:
        print("\nHow to Fix / Recommended Steps:")
        for fix_idx, step in enumerate(top_fixes, 1):
            print(f"  {fix_idx}. {step}")

    print("\nSummary:")
    print(analysis.get("summary", "Analysis complete."))

    print(f"\nEnough evidence: {analysis.get('enough_evidence', False)}")

    next_actions = analysis.get("next_actions", [])
    if next_actions:
        print("\nRecommended next diagnostic actions:")
        for action in next_actions:
            cid = action.get("command_id")
            opts = action.get("options", [])
            reason = action.get("reason", "")

            if not cid:
                print(f"- {reason}")
                continue

            cmd_str = cid + (" " + " ".join(opts) if opts else "")
            print(f"- ${cmd_str}")
            if reason:
                print(f"  Reason: {reason}")


def main() -> None:
    print("LocalOps Linux Troubleshooting Agent")
    print("=" * 60)

    # Health check for local Ollama
    is_ready, msg = check_ollama()
    if not is_ready:
        print("\n[Notice] Local Ollama SLM is not active.")
        print("LocalOps will operate in deterministic offline knowledge mode.")

    try:
        user_request = input(
            "\nWhat problem are you experiencing?\n> "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        print("\n\nLocalOps cancelled.")
        return

    if not user_request:
        print("No request provided. Exiting.")
        return

    # 1. PLANNER
    print("\n[1/5] Creating troubleshooting plan...")
    try:
        plan = create_plan(user_request)
    except Exception as error:
        print(f"\nPlanner error: {error}")
        return

    print("Plan created.")

    # 2. VALIDATOR
    print("\n[2/5] Validating troubleshooting plan...")
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
            print(f"\nPlan rejected by validator: {error}")
            return

    print(f"Plan validated: {len(validated_commands)} command(s).")
    print_plan(validated_commands)

    # 3. USER CONFIRMATION
    print("\n[3/5] Requesting permission...")
    try:
        approved = confirm_plan(validated_commands)
    except (KeyboardInterrupt, EOFError):
        print("\n\nExecution cancelled by user.")
        return

    if not approved:
        print("\nExecution cancelled by user. No commands were run.")
        return

    print("\nPermission granted.")

    # 4. EXECUTOR
    print("\n[4/5] Executing commands...")
    try:
        results = execute_plan(validated_commands, confirm=True)
    except Exception as error:
        print(f"\nExecution error: {error}")
        return

    print_results(results)

    # 5. ANALYZER
    print("\n[5/5] Analyzing results...")
    try:
        analysis = analyze_results(user_request, results)
    except Exception as error:
        print(f"\nAnalyzer error: {error}")
        return

    print_analysis(analysis)


if __name__ == "__main__":
    main()
