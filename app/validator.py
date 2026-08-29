from .knowledge import get_command


def validate_plan(plan):

    if not isinstance(plan, dict):
        raise ValueError("Plan must be a dictionary.")

    required_fields = [
        "problem",
        "assessment",
        "workflow_id",
        "commands"
    ]

    for field in required_fields:
        if field not in plan:
            raise ValueError(
                f"Plan is missing '{field}'."
            )

    if not isinstance(plan["commands"], list):
        raise ValueError(
            "'commands' must be a list."
        )

    validated = []

    for item in plan["commands"]:

        if not isinstance(item, dict):
            raise ValueError(
                "Invalid command entry."
            )

        command_id = item.get("command_id")
        command = item.get("command")

        if not command_id:
            raise ValueError(
                "Command is missing command_id."
            )

        if not command:
            raise ValueError(
                f"Command '{command_id}' is missing command."
            )

        knowledge = get_command(command_id)

        if knowledge is None:
            raise ValueError(
                f"Unknown command ID: {command_id}"
            )

        examples = set(
            knowledge.get(
                "combinations", {}
            ).get(
                "examples", []
            )
        )

        if command not in examples:
            raise ValueError(
                f"Command not allowed: '{command}' "
                f"for command ID '{command_id}'"
            )

        validated.append(
            {
                "command_id": command_id,
                "command": command,
                "description": knowledge.get(
                    "description", ""
                ),
                "purpose": item.get(
                    "purpose", ""
                ),
                "risk": knowledge.get(
                    "risk", "unknown"
                ),
                "read_only": knowledge.get(
                    "read_only", False
                ),
                "requires_sudo": knowledge.get(
                    "requires_sudo", False
                ),
                "requires_confirmation": knowledge.get(
                    "requires_confirmation", True
                )
            }
        )

    return validated
