from .planner import create_plan
from .validator import validate_plan
from .confirm import confirm_plan
from .executor import execute_plan
from .analyzer import analyze_results


def print_plan(commands: list[dict]) -> None:
    print()
    print("TROUBLESHOOTING PLAN")
    print("=" * 60)

    for index, command in enumerate(commands, 1):
        print(
            f"{index}. ${command['command']}"
        )

        purpose = command.get(
            "purpose",
            "",
        )

        if purpose:
            print(
                f"   Purpose: {purpose}"
            )


def print_results(results: list[dict]) -> None:
    print()
    print("COMMAND RESULTS")
    print("=" * 60)

    for index, result in enumerate(results, 1):

        print(
            f"\n[{index}] ${result['command']}"
        )

        print(
            f"Exit code: {result['return_code']}"
        )

        print(
            f"Success: {result['success']}"
        )

        if result["stdout"]:
            print("\nOutput:")
            print(result["stdout"])

        if result["stderr"]:
            print("\nError output:")
            print(result["stderr"])


def print_analysis(analysis: dict) -> None:
    print()
    print("LOCALOPS DIAGNOSIS")
    print("=" * 60)

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
            f"Confidence: "
            f"{item.get('confidence', 'unknown')}"
        )

        print(
            f"Evidence: "
            f"{item.get('evidence', '')}"
        )

    print()
    print("Summary:")
    print(analysis["summary"])

    print()
    print(
        "Enough evidence: "
        f"{analysis['enough_evidence']}"
    )

    if analysis["next_actions"]:

        print()
        print("Recommended next actions:")

        for action in analysis["next_actions"]:

            command_id = action.get(
                "command_id"
            )

            options = action.get(
                "options",
                [],
            )

            reason = action.get(
                "reason",
                "",
            )

            if command_id is None:
                print(
                    f"- {reason}"
                )
                continue

            command = command_id

            if options:
                command += " " + " ".join(options)

            print(
                f"- ${command}"
            )

            print(
                f"  Reason: {reason}"
            )


def main():
    print("LocalOps Linux Troubleshooting Agent")
    print("=" * 60)

    user_request = input(
        "\nWhat problem are you experiencing?\n> "
    ).strip()

    if not user_request:
        print("No request provided.")
        return

    # --------------------------------------------------
    # 1. PLANNER
    # --------------------------------------------------

    print("\n[1/5] Creating troubleshooting plan...")

    try:
        plan = create_plan(user_request)

    except Exception as error:
        print(
            f"\nPlanner error: {error}"
        )
        return

    print("Plan created.")

    # --------------------------------------------------
    # 2. VALIDATOR
    # --------------------------------------------------

    print(
        "\n[2/5] Validating troubleshooting plan..."
    )

    try:
        validated_commands = validate_plan(plan)

    except Exception as error:
        print(
            f"\nPlan rejected by validator: {error}"
        )
        return

    print(
        f"Plan validated: "
        f"{len(validated_commands)} command(s)"
    )

    print_plan(validated_commands)

    # --------------------------------------------------
    # 3. USER CONFIRMATION
    # --------------------------------------------------

    print(
        "\n[3/5] Requesting permission..."
    )

    approved = confirm_plan(
        validated_commands
    )

    if not approved:
        print(
            "\nExecution cancelled by user."
        )
        return

    print(
        "\nPermission granted."
    )

    # --------------------------------------------------
    # 4. EXECUTOR
    # --------------------------------------------------

    print(
        "\n[4/5] Executing commands..."
    )

    try:
        results = execute_plan(
            validated_commands,
            confirm=True,
        )

    except Exception as error:
        print(
            f"\nExecution error: {error}"
        )
        return

    print_results(results)

    # --------------------------------------------------
    # 5. ANALYZER
    # --------------------------------------------------

    print(
        "\n[5/5] Analyzing results with SLM..."
    )

    try:
        analysis = analyze_results(
            user_request,
            results,
        )

    except Exception as error:
        print(
            f"\nAnalyzer error: {error}"
        )
        return

    print_analysis(analysis)


if __name__ == "__main__":
    main()
