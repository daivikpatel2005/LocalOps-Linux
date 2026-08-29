import shlex
import subprocess
import time
from datetime import datetime


def execute_command(command):
    """
    Execute one validated command.

    IMPORTANT:
    This function expects a command that has already passed
    validator.validate_plan().
    """

    if not isinstance(command, str):
        raise ValueError(
            "Command must be a string."
        )

    if ";" in command or "&&" in command or "||" in command:
        raise ValueError(
            "Command chaining is not allowed."
        )

    if "|" in command:
        raise ValueError(
            "Shell pipelines are not allowed."
        )

    args = shlex.split(command)

    if not args:
        raise ValueError(
            "Cannot execute an empty command."
        )

    started = time.monotonic()

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )

        duration = time.monotonic() - started

        return {
            "command": command,
            "started_at": datetime.now().isoformat(),
            "duration_seconds": round(
                duration,
                3
            ),
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }

    except subprocess.TimeoutExpired as error:
        duration = time.monotonic() - started

        return {
            "command": command,
            "started_at": datetime.now().isoformat(),
            "duration_seconds": round(
                duration,
                3
            ),
            "return_code": None,
            "stdout": error.stdout or "",
            "stderr": "Command timed out.",
            "success": False
        }


def execute_plan(validated_commands):
    """
    Execute a validated plan after explicit user approval.
    """

    if not validated_commands:
        print("\nNo commands to execute.")
        return []

    print("\n")
    print("─────────────────────────────────────")
    print("EXECUTION")
    print("─────────────────────────────────────")

    for index, item in enumerate(
        validated_commands,
        1
    ):
        print(
            f"{index}. $ {item['command']}"
        )

    print("─────────────────────────────────────")

    answer = input(
        "Execute this plan? [y/N]: "
    ).strip().lower()

    if answer not in ("y", "yes"):
        print("\nExecution cancelled.")
        return []

    results = []

    for item in validated_commands:
        command = item["command"]

        print(f"\n$ {command}")

        result = execute_command(command)

        results.append(result)

        if result["stdout"]:
            print(result["stdout"], end="")

        if result["stderr"]:
            print(
                result["stderr"],
                end=""
            )

        print(
            f"[exit code: {result['return_code']}]"
        )

    return results
