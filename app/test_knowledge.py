from .knowledge import (
    load_knowledge,
    get_commands,
    get_workflows,
    get_command,
    find_workflow
)


def main():
    knowledge = load_knowledge()
    commands = get_commands()
    workflows = get_workflows()

    print(
        "Schema:",
        knowledge["schema_version"]
    )

    print(
        "Total commands:",
        len(commands)
    )

    print(
        "Total workflows:",
        len(workflows)
    )

    print(
        "\nDoes 'df' exist?"
    )

    print(
        get_command("df") is not None
    )

    print(
        "\nDF description:"
    )

    print(
        get_command("df")["description"]
    )

    print(
        "\nDF options:"
    )

    print(
        get_command("df")["options"]
    )

    print(
        "\nSystem slow workflow:"
    )

    workflow_id, workflow = find_workflow(
        "why is my system slow?"
    )

    print(
        "Workflow ID:",
        workflow_id
    )

    print(
        "Workflow:",
        workflow
    )


if __name__ == "__main__":
    main()
