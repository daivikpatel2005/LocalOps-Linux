import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_FILE = BASE_DIR / "knowledge" / "commands.json"


def load_knowledge():
    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def get_commands():
    return load_knowledge()["commands"]


def get_workflows():
    return load_knowledge().get("workflows", {})


def get_command(command_id):
    return get_commands().get(command_id)


def get_workflow(workflow_id):
    return get_workflows().get(workflow_id)


def find_workflow(user_request):
    """
    Deterministically find a workflow using trigger matching.

    Returns:
        (workflow_id, workflow)
        or
        (None, None)
    """

    request = user_request.lower().strip()

    workflows = get_workflows()

    for workflow_id, workflow in workflows.items():
        for trigger in workflow.get("triggers", []):
            if trigger.lower() in request:
                return workflow_id, workflow

    return None, None


def build_context():
    knowledge = load_knowledge()

    return json.dumps(
        {
            "workflows": knowledge.get("workflows", {}),
            "commands": knowledge.get("commands", {})
        },
        indent=2
    )
