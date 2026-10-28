"""Command execution engine for LocalOps.

Executes only validated, allow-listed, read-only diagnostic commands using argv vectors
with shell=False. Enforces strict timeouts, output truncation, independent safety gates,
and explicit confirmation before execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
import subprocess
import time
from typing import Any, Optional

from .config import COMMAND_TIMEOUT_SECONDS, MAX_OUTPUT_BYTES


class ExecutionError(Exception):
    """Raised when an invalid command or unapproved execution is attempted."""
    pass


def _truncate_output(text: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    """Safely truncate excessively large command output to prevent memory exhaustion."""
    if not isinstance(text, str):
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text

    truncated_encoded = encoded[:max_bytes]
    decoded = truncated_encoded.decode("utf-8", errors="replace")
    return decoded + f"\n... [Output truncated: exceeded {max_bytes} bytes]"


def execute_command(
    command: dict[str, Any],
    timeout_seconds: Optional[int] = None,
) -> dict[str, Any]:
    """
    Execute one pre-validated diagnostic command.

    Accepts ONLY a normalized dictionary created by validator.validate_plan().
    Enforces independent defense-in-depth safety checks:
    - Must have validation metadata.
    - read_only must be strictly True.
    - requires_sudo must be strictly False.
    - shell=False execution with argv vector.
    """
    if not isinstance(command, dict):
        raise ExecutionError("Command object must be a dictionary.")

    command_id = command.get("command_id")
    shell_command = command.get("command")

    if not command_id or not isinstance(command_id, str):
        raise ExecutionError("Command object missing 'command_id'.")

    if not shell_command or not isinstance(shell_command, str):
        raise ExecutionError(f"Command '{command_id}' missing 'command' string.")

    # Defense in depth: Verify validator safety metadata
    if "risk" not in command:
        raise ExecutionError(
            f"Command '{command_id}' does not contain required validation metadata."
        )

    if command.get("read_only") is not True:
        raise ExecutionError(
            f"Command '{command_id}' is not read-only. Non-read-only execution is prohibited."
        )

    if command.get("requires_sudo") is True:
        raise ExecutionError(
            f"Command '{command_id}' requires sudo. Privilege escalation is prohibited."
        )

    # Use pre-constructed argv from validator if available, else split safely
    argv = command.get("argv")
    if not argv or not isinstance(argv, list):
        argv = shell_command.split()

    if not argv:
        raise ExecutionError(f"Empty command argv for '{command_id}'.")

    # Defense in depth: Verify executable matches command_id
    if argv[0] != command_id:
        raise ExecutionError(
            f"Executable mismatch: argv[0]='{argv[0]}' does not match command_id='{command_id}'."
        )

    timeout = timeout_seconds or COMMAND_TIMEOUT_SECONDS
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.monotonic()

    try:
        process = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        duration = round(time.monotonic() - start_time, 3)

        stdout = _truncate_output(process.stdout.strip())
        stderr = _truncate_output(process.stderr.strip())
        return_code = process.returncode

        return {
            "command_id": command_id,
            "command": shell_command,
            "argv": argv,
            "started_at": started_at,
            "duration_seconds": duration,
            "return_code": return_code,
            "exit_code": return_code,  # Alias to prevent KeyError
            "stdout": stdout,
            "stderr": stderr,
            "success": (return_code == 0),
            "timed_out": False,
        }

    except subprocess.TimeoutExpired as err:
        duration = round(time.monotonic() - start_time, 3)
        raw_stdout = err.stdout.decode("utf-8", errors="replace") if isinstance(err.stdout, bytes) else (err.stdout or "")
        raw_stderr = err.stderr.decode("utf-8", errors="replace") if isinstance(err.stderr, bytes) else (err.stderr or "")

        return {
            "command_id": command_id,
            "command": shell_command,
            "argv": argv,
            "started_at": started_at,
            "duration_seconds": duration,
            "return_code": 124,
            "exit_code": 124,
            "stdout": _truncate_output(raw_stdout.strip()),
            "stderr": f"Command timed out after {timeout} seconds. {raw_stderr}".strip(),
            "success": False,
            "timed_out": True,
        }

    except FileNotFoundError:
        duration = round(time.monotonic() - start_time, 3)
        return {
            "command_id": command_id,
            "command": shell_command,
            "argv": argv,
            "started_at": started_at,
            "duration_seconds": duration,
            "return_code": 127,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"Command not found on system: '{command_id}'",
            "success": False,
            "timed_out": False,
        }

    except OSError as err:
        duration = round(time.monotonic() - start_time, 3)
        return {
            "command_id": command_id,
            "command": shell_command,
            "argv": argv,
            "started_at": started_at,
            "duration_seconds": duration,
            "return_code": -1,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"OS execution error: {err}",
            "success": False,
            "timed_out": False,
        }


def execute_plan(
    commands: list[dict[str, Any]],
    confirm: bool = False,
    timeout_seconds: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Execute a list of validated commands in sequence.

    Execution is strictly disabled unless confirm is explicitly True.
    """
    if not isinstance(commands, list):
        raise ExecutionError("Commands argument must be a list.")

    if not commands:
        raise ExecutionError("Cannot execute an empty command list.")

    if confirm is not True:
        raise ExecutionError(
            "Security rule violation: Execution requires explicit user confirmation (confirm=True)."
        )

    results: list[dict[str, Any]] = []

    for command in commands:
        result = execute_command(command, timeout_seconds=timeout_seconds)
        results.append(result)

    return results
