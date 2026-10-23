from .knowledge import get_command, get_workflow


def validate_plan(plan):
    """
    Validate an SLM-generated troubleshooting plan.

    The validator is the security boundary between
    the SLM and the command executor.
    """

    if not isinstance(plan, dict):
        raise ValueError("Plan must be a dictionary.")

    if "problem" not in plan:
        raise ValueError("Plan is missing 'problem'.")

    if "assessment" not in plan:
        raise ValueError("Plan is missing 'assessment'.")

    if "plan" not in plan:
        raise ValueError("Plan is missing 'plan'.")

    if not isinstance(plan["plan"], list):
        raise ValueError("'plan' must be a list.")

    workflow_id = plan.get("workflow_id")

    if workflow_id is not None:
        if not isinstance(workflow_id, str):
            raise ValueError("'workflow_id' must be a string.")

        if get_workflow(workflow_id) is None:
            raise ValueError(
                f"Unknown workflow ID: {workflow_id}"
            )

    validated = []

    for index, item in enumerate(plan["plan"], 1):

        if not isinstance(item, dict):
            raise ValueError(
                f"Plan item {index} must be an object."
            )

        command_id = item.get("command_id")
        options = item.get("options")
        purpose = item.get("purpose", "")

        if not command_id:
            raise ValueError(
                f"Plan item {index} is missing command_id."
            )

        if not isinstance(command_id, str):
            raise ValueError(
                f"Command ID for item {index} must be a string."
            )

        # command_id must ONLY contain the command name.
        if " " in command_id or "\t" in command_id:
            raise ValueError(
                f"Invalid command_id '{command_id}'. "
                "command_id must contain only the command ID."
            )

        if options is None:
            raise ValueError(
                f"Command '{command_id}' is missing options."
            )

        if not isinstance(options, list):
            raise ValueError(
                f"Options for '{command_id}' must be a list."
            )

        knowledge = get_command(command_id)

        if knowledge is None:
            raise ValueError(
                f"Unknown command ID: {command_id}"
            )

        known_options = knowledge.get("options", {})

        if not isinstance(known_options, dict):
            raise ValueError(
                f"Knowledge options for '{command_id}' "
                "must be an object."
            )

        # Validate every requested option.
        for option in options:

            if not isinstance(option, str):
                raise ValueError(
                    f"Invalid option for '{command_id}'."
                )

            if option not in known_options:
                raise ValueError(
                    f"Option '{option}' is not allowed for "
                    f"command '{command_id}'."
                )

            option_definition = known_options[option]

            if not isinstance(option_definition, dict):
                raise ValueError(
                    f"Invalid option definition for "
                    f"'{command_id}': '{option}'."
                )

            required_options = option_definition.get(
                "requires",
                []
            )

            for required in required_options:

                if required not in options:
                    raise ValueError(
                        f"Option '{option}' for '{command_id}' "
                        f"requires '{required}'."
                    )

        # Build the exact command from the knowledge base.
        examples = (
            knowledge
            .get("combinations", {})
            .get("examples", [])
        )

        if not isinstance(examples, list):
            raise ValueError(
                f"Invalid command examples for '{command_id}'."
            )

        expected_command = command_id

        if options:
            expected_command += " " + " ".join(options)

        if expected_command not in examples:
            raise ValueError(
                "Command combination not allowed: "
                f"'{expected_command}'"
            )

        validated.append(
            {
                "command_id": command_id,
                "command": expected_command,
                "purpose": purpose,
                "description": knowledge.get(
                    "description",
                    ""
                ),
                "risk": knowledge.get(
                    "risk",
                    "unknown"
                ),
                "read_only": knowledge.get(
                    "read_only",
                    False
                ),
                "requires_sudo": knowledge.get(
                    "requires_sudo",
                    False
                ),
                "requires_confirmation": knowledge.get(
                    "requires_confirmation",
                    True
                ),
                "options": options,
            }
        )

    if not validated:
        raise ValueError(
            "The troubleshooting plan contains no commands."
        )

    return validated
