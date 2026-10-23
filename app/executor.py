import subprocess


class ExecutionError(Exception):
    """Raised when a command cannot be executed safely."""
    pass


def execute_command(command: dict) -> dict:
    """
    Execute one command that has already passed validation.

    The executor accepts ONLY the normalized command dictionary
    returned by validator.validate_plan().
    """

    if not isinstance(command, dict):
        raise ExecutionError(
            "Invalid command object."
        )

    command_id = command.get("command_id")
    shell_command = command.get("command")

    if not command_id:
        raise ExecutionError(
            "Missing command_id."
        )

    if not shell_command:
        raise ExecutionError(
            f"Command '{command_id}' has no command."
        )

    # Defense in depth:
    # Executor only accepts commands containing
    # validator-generated metadata.
    if "risk" not in command:
        raise ExecutionError(
            f"Command '{command_id}' does not contain "
            "validation metadata."
        )

    if command.get("read_only") is not True:
        raise ExecutionError(
            f"Command '{command_id}' is not read-only. "
            "Non-read-only execution is disabled."
        )

    if command.get("requires_sudo") is True:
        raise ExecutionError(
            f"Command '{command_id}' requires sudo. "
            "Sudo execution is disabled."
        )

    # --------------------------------------------------
    # Convert validated command to argv
    # --------------------------------------------------

    try:
        argv = shell_command.split()

    except Exception as error:
        raise ExecutionError(
            f"Could not parse command "
            f"'{shell_command}': {error}"
        ) from error

    if not argv:
        raise ExecutionError(
            "Empty command."
        )

    # --------------------------------------------------
    # Execute
    # --------------------------------------------------

    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    except subprocess.TimeoutExpired as error:
        raise ExecutionError(
            f"Command timed out after 30 seconds: "
            f"{shell_command}"
        ) from error

    except OSError as error:
        raise ExecutionError(
            f"Failed to execute "
            f"'{shell_command}': {error}"
        ) from error

    # --------------------------------------------------
    # Return normalized execution result
    # --------------------------------------------------

    return {
        "command_id": command_id,
        "command": shell_command,
        "return_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "success": result.returncode == 0,
    }


def execute_plan(
    commands: list[dict],
    confirm: bool = False,
) -> list[dict]:
    """
    Execute a validated plan.

    Execution is disabled unless confirm=True.
    """

    if not isinstance(commands, list):
        raise ExecutionError(
            "Commands must be a list."
        )

    if not confirm:
        raise ExecutionError(
            "Execution requires explicit confirmation."
        )

    results = []

    for command in commands:
        result = execute_command(command)
        results.append(result)

    return results
