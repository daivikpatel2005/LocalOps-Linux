import json

from .llm import ask
from .knowledge import build_context, find_workflow


SYSTEM_PROMPT = """
You are the planning engine for LocalOps, an offline Linux
troubleshooting agent.

Your job is to analyze the user's problem and create a safe
diagnostic plan using ONLY commands from the provided knowledge base.

The knowledge base is the authority for:

- valid command IDs
- valid options
- command combinations
- workflow candidate commands
- command safety metadata

IMPORTANT RULES:

1. Return ALL required top-level fields.
2. The required top-level fields are:
   - problem
   - assessment
   - workflow_id
   - plan

3. Never invent a command.
4. Never invent a command ID.
5. command_id MUST contain ONLY the command ID.
6. NEVER put options or arguments inside command_id.
7. Options MUST be returned separately in the options array.
8. Only use command IDs present in the knowledge base.
9. Only use options defined for that command.
10. Never execute commands.
11. Never suggest shell pipelines.
12. Never suggest command chaining.
13. Keep the assessment short.
14. The plan must contain actual diagnostic commands.
15. Return ONLY valid JSON.
16. Do not return markdown.
17. Do not return code fences.
18. Do not return explanations outside the JSON object.

WORKFLOW RULES:

If a workflow matches the user's problem:

- Return its workflow_id.
- Use the workflow's candidate_commands as the available
  diagnostic commands.
- For a broad/general problem, include ALL relevant candidate
  commands from that workflow.
- Do NOT arbitrarily return only one or two commands when the
  workflow provides multiple relevant diagnostic commands.
- For a specific problem, use only commands relevant to that
  specific problem.
- Do not add commands that are not candidates of the selected
  workflow unless they are directly present and appropriate in
  the knowledge base.

For example, for the system_slow workflow:

candidate_commands:
[
    "uptime",
    "free",
    "df",
    "ps"
]

For a general request such as:

"why is my system slow"

the plan should normally contain all four diagnostic commands.

IMPORTANT:

The number of commands is NOT determined by how short the answer
can be.

The goal is to create a complete first diagnostic pass.

OUTPUT FORMAT:

{
    "problem": "short description",
    "assessment": "short assessment",
    "workflow_id": "workflow ID or null",
    "plan": [
        {
            "command_id": "uptime",
            "options": [],
            "purpose": "Check system load"
        }
    ]
}

MANDATORY:

The JSON object MUST contain:

"problem"
"assessment"
"workflow_id"
"plan"

The plan MUST be a JSON array.

Every plan item MUST contain:

"command_id"
"options"
"purpose"

The command_id must exactly match a key in the knowledge base.

The options field must always be a JSON array.

If no options are required:

"options": []

If options are required:

"options": ["-h"]

Do not return a "command" field.

Do not return command descriptions.

Do not return risk information.

Do not return validation metadata.

Those fields are added by the LocalOps validator.
"""


def create_plan(user_request: str):
    """
    Ask the local SLM to create a troubleshooting plan.

    The SLM chooses the workflow and diagnostic commands.
    The validator later decides whether the generated plan
    is actually allowed.
    """

    if not isinstance(user_request, str):
        raise ValueError(
            "User request must be a string."
        )

    user_request = user_request.strip()

    if not user_request:
        raise ValueError(
            "User request cannot be empty."
        )

    knowledge = build_context()

    workflow_id, workflow = find_workflow(
        user_request
    )

    workflow_context = {
        "matched_workflow_id": workflow_id,
        "matched_workflow": workflow,
    }

    prompt = f"""
{SYSTEM_PROMPT}

KNOWLEDGE BASE:
{knowledge}

PRE-MATCHED WORKFLOW INFORMATION:
{json.dumps(workflow_context, indent=2)}

USER REQUEST:
{user_request}

Create the COMPLETE first diagnostic plan.

The response MUST contain these four top-level fields:

1. problem
2. assessment
3. workflow_id
4. plan

If the matched workflow is "system_slow", this is a broad
system-performance investigation.

Include all relevant candidate diagnostic commands from that
workflow.

Return ONLY the JSON object.
""".strip()

    response = ask(prompt).strip()

    # Defensive cleanup in case the model returns markdown fences.
    if response.startswith("```"):
        lines = response.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        response = "\n".join(lines).strip()

    try:
        plan = json.loads(response)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "SLM returned invalid JSON:\n\n"
            + response
        ) from error

    if not isinstance(plan, dict):
        raise RuntimeError(
            "SLM returned JSON, but the result is not an object."
        )

    # Check the planner's required structure immediately.
    # This gives a clearer error before the validator runs.
    required_fields = [
        "problem",
        "assessment",
        "workflow_id",
        "plan",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in plan
    ]

    if missing_fields:
        raise RuntimeError(
            "SLM planner response is missing required field(s): "
            + ", ".join(missing_fields)
            + "\n\nRaw response:\n"
            + response
        )

    if not isinstance(plan["problem"], str):
        raise RuntimeError(
            "Planner field 'problem' must be a string."
        )

    if not isinstance(plan["assessment"], str):
        raise RuntimeError(
            "Planner field 'assessment' must be a string."
        )

    if plan["workflow_id"] is not None and not isinstance(
        plan["workflow_id"],
        str,
    ):
        raise RuntimeError(
            "Planner field 'workflow_id' must be a string or null."
        )

    if not isinstance(plan["plan"], list):
        raise RuntimeError(
            "Planner field 'plan' must be a list."
        )

    if not plan["plan"]:
        raise RuntimeError(
            "SLM planner returned an empty diagnostic plan."
        )

    return plan
