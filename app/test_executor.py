from app.executor import execute_plan
from app.validator import validate_plan


plan = {
    "problem": "Test system diagnostics",
    "assessment": "Testing safe read-only diagnostic commands.",
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

        print(
            f"[{index}/{len(results)}] "
            f"${result['command']}"
        )

        print(
            f"Exit code: {result['exit_code']}"
        )

        print(
            f"Success: {result['success']}"
        )

        if result["stdout"]:
            print()
            print("Output:")
            print(result["stdout"])

        if result["stderr"]:
            print()
            print("Error:")
            print(result["stderr"])

        print()

except Exception as error:
    print()
    print("EXECUTION FAILED")
    print(error)


print("─────────────────────────────────────")
print("Executor test complete")
print("─────────────────────────────────────")
