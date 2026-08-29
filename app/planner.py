import json

from .llm import ask
from .knowledge import (
    get_workflow,
    get_command,
)


SYSTEM_PROMPT = """
You are the intent classification engine for LocalOps.

LocalOps is a Linux troubleshooting agent.

Your job is ONLY to identify which troubleshooting workflow best matches
the user's request.

Do NOT select individual commands.

Do NOT invent workflows.

Do NOT explain commands.

Return ONLY valid JSON.

Return exactly:

{
  "workflow_id": "system_slow",
  "problem": "short description",
  "assessment": "short assessment"
}

The workflow_id MUST be one of the workflow IDs provided in the knowledge base.

If no workflow clearly matches, return:

{
  "workflow_id": null,
  "problem": "short description",
  "assessment": "No supported troubleshooting workflow was identified."
}
"""


def _clean_json(response):
    response = response.strip()

    if response.startswith("```"):
        response = response.replace("```json", "", 1)
        response = response.replace("```", "", 1)
        response = response.strip()

    return response


def _ask_workflow(user_request):
    from .knowledge import get_workflows

    workflows = get_workflows()

    workflow_summary = {}

    for workflow_id, workflow in workflows.items():
        workflow_summary[workflow_id] = {
            "description": workflow.get("description", ""),
            "triggers": workflow.get("triggers", [])
        }

    prompt = f"""
{SYSTEM_PROMPT}

AVAILABLE WORKFLOWS:

{json.dumps(workflow_summary, indent=2)}

USER REQUEST:

{user_request}

Identify the best matching workflow.
"""

    response = ask(prompt)

    response = _clean_json(response)

    try:
        return json.loads(response)

    except json.JSONDecodeError:
        raise RuntimeError(
            "SLM returned invalid JSON:\n\n" + response
        )


def create_plan(user_request):

    if not user_request.strip():
        raise ValueError("User request cannot be empty.")

    # ---------------------------------------------------------
    # Step 1: Let the SLM understand the user's intent.
    # ---------------------------------------------------------

    intent = _ask_workflow(user_request)

    workflow_id = intent.get("workflow_id")

    if not workflow_id:
        raise ValueError(
            "No supported troubleshooting workflow was identified."
        )

    # ---------------------------------------------------------
    # Step 2: Python validates the workflow.
    # ---------------------------------------------------------

    workflow = get_workflow(workflow_id)

    if workflow is None:
        raise ValueError(
            f"SLM selected unknown workflow: {workflow_id}"
        )

    # ---------------------------------------------------------
    # Step 3: Python deterministically builds the command plan.
    # ---------------------------------------------------------

    commands = []

    for candidate in workflow.get("candidate_commands", []):

        command_info = get_command(candidate)

        if command_info is None:
            raise ValueError(
                f"Workflow '{workflow_id}' references "
                f"unknown command '{candidate}'"
            )

        examples = command_info.get(
            "combinations", {}
        ).get("examples", [])

        if not examples:
            raise ValueError(
                f"Command '{candidate}' has no valid examples."
            )

        # Choose the first documented safe example.
        command = examples[0]

        # Prefer human-readable option where appropriate.
        if "-h" in examples:
            command = f"{candidate} -h"

        if candidate == "ps" and "ps aux" in examples:
            command = "ps aux"

        commands.append(
            {
                "command_id": candidate,
                "command": command,
                "description": command_info["description"],
                "purpose": _get_command_purpose(
                    workflow,
                    candidate
                ),
                "risk": command_info.get("risk"),
                "read_only": command_info.get(
                    "read_only", False
                ),
                "requires_sudo": command_info.get(
                    "requires_sudo", False
                ),
                "requires_confirmation": command_info.get(
                    "requires_confirmation", True
                )
            }
        )

    return {
        "problem": intent.get(
            "problem",
            workflow["description"]
        ),
        "assessment": intent.get(
            "assessment",
            workflow["description"]
        ),
        "workflow_id": workflow_id,
        "commands": commands
    }


def _get_command_purpose(workflow, command_id):

    purposes = {
        "uptime": "Check system load",
        "free": "Check RAM and swap pressure",
        "df": "Check filesystem capacity",
        "ps": "Find resource-heavy processes",
        "ls": "Inspect files and directories"
    }

    return purposes.get(
        command_id,
        f"Collect information about {command_id}"
    )
