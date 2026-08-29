from .planner import create_plan
from .validator import validate_plan
from .executor import execute_plan
from .diagnostician import diagnose


def print_plan(plan, validated_commands):
    print("\n")
    print("─────────────────────────────────────")
    print("PLAN")
    print("─────────────────────────────────────")

    print("\nProblem:")
    print(plan["problem"])

    print("\nAssessment:")
    print(plan["assessment"])

    if plan.get("workflow"):
        print(
            f"\nWorkflow: {plan['workflow']}"
        )

    print("\nCommands:")

    for index, item in enumerate(
        validated_commands,
        1
    ):
        print(
            f"\n{index}. $ {item['command']}"
        )

        print(
            f"   What: {item['description']}"
        )

        print(
            f"   Why:  {item['purpose']}"
        )

        print(
            f"   Risk: {item['risk']}"
        )

        print(
            f"   Read-only: {item['read_only']}"
        )

    print(
        "\n─────────────────────────────────────"
    )


def run_agent(user_request):
    print(
        "\nLocalOps is thinking..."
    )

    plan = create_plan(
        user_request
    )

    validated_commands = validate_plan(
        plan
    )

    print_plan(
        plan,
        validated_commands
    )

    results = execute_plan(
        validated_commands
    )

    if not results:
        return

    print("\n")
    print("─────────────────────────────────────")
    print("ANALYZING RESULTS")
    print("─────────────────────────────────────")

    diagnosis = diagnose(
        user_request,
        results
    )

    print(
        f"\nStatus: {diagnosis.get('status')}"
    )

    print(
        f"Diagnosis: {diagnosis.get('diagnosis')}"
    )

    print("\nEvidence:")

    for evidence in diagnosis.get(
        "evidence",
        []
    ):
        print(
            f"- {evidence}"
        )

    print(
        f"\nSeverity: {diagnosis.get('severity')}"
    )

    print(
        f"Next step: {diagnosis.get('next_step')}"
    )

    print(
        "\n─────────────────────────────────────"
    )
