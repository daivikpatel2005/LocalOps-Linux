"""Validator module for LocalOps.

Acts as the security boundary between the planning layer and the execution layer.
Enforces strict allow-lists, trusted metadata assignment, option dependencies,
combination approvals, and rejects shell metacharacters and privilege escalation.
"""

from __future__ import annotations

import re
from typing import Any

from .knowledge import get_command, get_workflow

# Prohibit any shell control or pipeline characters in commands or options
UNSAFE_CHARS_PATTERN = re.compile(r"[;\|\&\>\<\$\`\(\)\{\}\\\n\r]")
MAX_PLAN_COMMANDS = 15


class ValidationError(ValueError):
    """Raised when a diagnostic plan violates security or schema rules."""
    pass


def validate_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Validate a troubleshooting plan against the trusted knowledge base.

    Returns:
        List of normalized, validated command dictionaries ready for execution.
    Raises:
        ValidationError: If any safety rule or schema constraint is violated.
    """
    if not isinstance(plan, dict):
        raise ValidationError("Plan must be a dictionary.")

    if "problem" not in plan or not isinstance(plan["problem"], str):
        raise ValidationError("Plan is missing a valid 'problem' string.")

    if "assessment" not in plan or not isinstance(plan["assessment"], str):
        raise ValidationError("Plan is missing a valid 'assessment' string.")

    if "plan" not in plan:
        raise ValidationError("Plan is missing 'plan'.")

    raw_plan = plan["plan"]
    if not isinstance(raw_plan, list):
        raise ValidationError("Plan field 'plan' must be a list.")

    if not raw_plan:
        raise ValidationError("The troubleshooting plan contains no commands.")

    if len(raw_plan) > MAX_PLAN_COMMANDS:
        raise ValidationError(
            f"Plan exceeds maximum allowed command count of {MAX_PLAN_COMMANDS} (got {len(raw_plan)})."
        )

    # Workflow validation
    workflow_id = plan.get("workflow_id")
    if workflow_id is not None:
        if not isinstance(workflow_id, str):
            raise ValidationError("Field 'workflow_id' must be a string or null.")

        if get_workflow(workflow_id) is None:
            raise ValidationError(
                f"Unknown workflow ID: '{workflow_id}'"
            )

    validated_commands: list[dict[str, Any]] = []

    for index, item in enumerate(raw_plan, 1):
        if not isinstance(item, dict):
            raise ValidationError(
                f"Plan item {index} must be an object, got {type(item).__name__}."
            )

        command_id = item.get("command_id")
        options = item.get("options")
        purpose = item.get("purpose", "")

        if not command_id or not isinstance(command_id, str):
            raise ValidationError(
                f"Plan item {index} has missing or invalid 'command_id'."
            )

        command_id = command_id.strip()

        # Reject whitespace, tabs, or shell metacharacters in command_id
        if re.search(r"\s", command_id):
            raise ValidationError(
                f"Invalid command_id '{command_id}': command_id must not contain whitespace."
            )

        if UNSAFE_CHARS_PATTERN.search(command_id):
            raise ValidationError(
                f"Invalid command_id '{command_id}': shell metacharacters are strictly forbidden."
            )

        if options is None or not isinstance(options, list):
            raise ValidationError(
                f"Command '{command_id}' must contain a list of 'options'."
            )

        # Retrieve trusted metadata from knowledge base
        knowledge = get_command(command_id)
        if knowledge is None:
            raise ValidationError(
                f"Unknown command ID: '{command_id}'. Only allow-listed commands are permitted."
            )

        # Enforce safety policy from trusted knowledge base
        if not knowledge.get("read_only", False):
            raise ValidationError(
                f"Command '{command_id}' is not read-only. Modifying commands are forbidden."
            )

        if knowledge.get("requires_sudo", False):
            raise ValidationError(
                f"Command '{command_id}' requires sudo. Privilege escalation is disabled."
            )

        known_options = knowledge.get("options", {})
        if not isinstance(known_options, dict):
            raise ValidationError(
                f"Knowledge base corruption: options for '{command_id}' must be an object."
            )

        # Validate options and check for unsafe characters
        validated_options: list[str] = []
        for option in options:
            if not isinstance(option, str):
                raise ValidationError(
                    f"Option in command '{command_id}' must be a string, got {type(option).__name__}."
                )

            opt_clean = option.strip()

            if UNSAFE_CHARS_PATTERN.search(opt_clean):
                raise ValidationError(
                    f"Option '{opt_clean}' for '{command_id}' contains forbidden shell characters."
                )

            if opt_clean not in known_options:
                # Normalization for SLMs that omit leading hyphens (e.g. 'brief' -> '-brief', 'h' -> '-h')
                if f"-{opt_clean}" in known_options:
                    opt_clean = f"-{opt_clean}"
                elif f"--{opt_clean}" in known_options:
                    opt_clean = f"--{opt_clean}"
                else:
                    raise ValidationError(
                        f"Option '{opt_clean}' is not allowed for command '{command_id}'."
                    )

            opt_def = known_options[opt_clean]
            if not isinstance(opt_def, dict):
                raise ValidationError(
                    f"Invalid option definition for '{command_id}': '{opt_clean}'."
                )

            # Check required option dependencies
            required_opts = opt_def.get("requires", [])
            for req in required_opts:
                if req not in options and req not in validated_options:
                    raise ValidationError(
                        f"Option '{opt_clean}' for '{command_id}' requires option '{req}'."
                    )

            validated_options.append(opt_clean)

        # Build normalized shell command representation
        expected_command = command_id
        if validated_options:
            expected_command += " " + " ".join(validated_options)

        # Verify combination is explicitly allow-listed in combinations.examples
        allowed_examples = (
            knowledge.get("combinations", {}).get("examples", [])
        )
        if not isinstance(allowed_examples, list) or expected_command not in allowed_examples:
            raise ValidationError(
                f"Command combination not allowed: '{expected_command}'. "
                f"Allowed examples: {allowed_examples}"
            )

        # Build trusted argv vector: [executable, *options]
        argv = [command_id] + list(validated_options)

        validated_commands.append(
            {
                "command_id": command_id,
                "command": expected_command,
                "argv": argv,
                "purpose": purpose if isinstance(purpose, str) else "",
                "description": knowledge.get("description", ""),
                "risk": knowledge.get("risk", "low"),
                "read_only": True,
                "requires_sudo": False,
                "requires_confirmation": knowledge.get(
                    "requires_confirmation", True
                ),
                "options": validated_options,
            }
        )

    return validated_commands
