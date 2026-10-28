from pathlib import Path
import sys

# Ensure repository root is on sys.path for direct execution
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.knowledge import (
    load_knowledge,
    get_commands,
    get_workflows,
    get_command,
    find_workflow,
)


def main():
    knowledge = load_knowledge()
    commands = get_commands()
    workflows = get_workflows()

    print(
        "Schema:",
        knowledge.get("schema_version", "1.0"),
    )

    print(
        "Total commands:",
        len(commands),
    )

    print(
        "Total workflows:",
        len(workflows),
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

    df_cmd = get_command("df")
    print(
        df_cmd.get("description", "") if df_cmd else "Command not found"
    )

    print(
        "\nDF options:"
    )

    print(
        df_cmd.get("options", {}) if df_cmd else {}
    )

    print(
        "\nSystem slow workflow:"
    )

    workflow_id, workflow = find_workflow(
        "why is my system slow?"
    )

    print(
        "Workflow ID:",
        workflow_id,
    )

    print(
        "Workflow:",
        workflow,
    )


if __name__ == "__main__":
    main()
