import json

from .llm import ask
from .knowledge import get_commands


def build_analysis_prompt(
    user_request: str,
    execution_results: list[dict],
) -> str:
    """
    Build the prompt used by the SLM analyzer.
    """

    commands = get_commands()

    available_commands = {}

    for command_id, command in commands.items():

        available_commands[command_id] = {
            "description": command.get(
                "description",
                "",
            ),
            "category": command.get(
                "category",
                "",
            ),
            "allowed_options": list(
                command.get(
                    "options",
                    {},
                ).keys()
            ),
            "read_only": command.get(
                "read_only",
                False,
            ),
            "requires_sudo": command.get(
                "requires_sudo",
                False,
            ),
        }

    results_json = json.dumps(
        execution_results,
        indent=2,
        ensure_ascii=False,
    )

    commands_json = json.dumps(
        available_commands,
        indent=2,
        ensure_ascii=False,
    )

    return f"""
You are the diagnostic analyzer for LocalOps,
a Linux troubleshooting agent.

Your job is to analyze real command output collected
from the user's Linux system.

Original user request:
{user_request}

AVAILABLE LOCALOPS COMMANDS:

{commands_json}

COMMAND EXECUTION RESULTS:

{results_json}

Analyze the evidence carefully.

RULES:

1. Only make claims supported by the command output.
2. Do not invent system information.
3. Distinguish observed evidence from possible causes.
4. Give confidence as low, medium, or high.
5. Give severity as low, medium, high, or critical.
6. If evidence is insufficient, say so.
7. Do not provide raw shell commands.
8. If more investigation is needed, recommend a command_id
   from AVAILABLE LOCALOPS COMMANDS.
9. The command_id MUST exactly match an available command.
10. Options MUST exactly match the allowed_options for that command.
11. Do NOT invent options.
12. Never recommend sudo.
13. Never recommend a command that is not available.
14. Do not execute anything.
15. If enough evidence exists, set enough_evidence to true.
16. If more evidence is required, set enough_evidence to false.

IMPORTANT:

For example, if df has allowed_options:

["-h"]

you may use:

"options": ["-h"]

You MUST NOT invent options such as:

"--details"
"--verbose"
"--all"

unless they are explicitly listed in allowed_options.

Return ONLY valid JSON.

Required format:

{{
  "diagnosis": [
    {{
      "problem": "short description",
      "severity": "low|medium|high|critical",
      "evidence": "specific evidence from command output",
      "confidence": "low|medium|high"
    }}
  ],
  "summary": "short overall explanation",
  "next_actions": [
    {{
      "command_id": "known command ID or null",
      "options": [],
      "reason": "why this diagnostic action is useful"
    }}
  ],
  "enough_evidence": true
}}
""".strip()


def validate_analysis(analysis: dict) -> dict:
    """
    Validate the structure of an SLM analyzer response.

    Invalid next actions are discarded instead of allowing
    them to stop an otherwise valid diagnosis.
    """

    if not isinstance(analysis, dict):
        raise ValueError(
            "Analyzer response must be a dictionary."
        )

    required_fields = [
        "diagnosis",
        "summary",
        "next_actions",
        "enough_evidence",
    ]

    for field in required_fields:
        if field not in analysis:
            raise ValueError(
                f"Analyzer response is missing '{field}'."
            )

    if not isinstance(
        analysis["diagnosis"],
        list,
    ):
        raise ValueError(
            "'diagnosis' must be a list."
        )

    if not isinstance(
        analysis["summary"],
        str,
    ):
        raise ValueError(
            "'summary' must be a string."
        )

    if not isinstance(
        analysis["next_actions"],
        list,
    ):
        raise ValueError(
            "'next_actions' must be a list."
        )

    if not isinstance(
        analysis["enough_evidence"],
        bool,
    ):
        raise ValueError(
            "'enough_evidence' must be a boolean."
        )

    commands = get_commands()

    valid_next_actions = []

    for index, action in enumerate(
        analysis["next_actions"],
        1,
    ):

        if not isinstance(action, dict):
            continue

        command_id = action.get(
            "command_id"
        )

        options = action.get(
            "options",
            [],
        )

        reason = action.get(
            "reason",
            "",
        )

        # No command means no executable next action.
        if command_id is None:
            continue

        # Unknown command.
        if command_id not in commands:
            print(
                f"\n[Analyzer] Rejected unknown "
                f"command: {command_id}"
            )
            continue

        if not isinstance(options, list):
            print(
                f"\n[Analyzer] Rejected invalid options "
                f"for '{command_id}'"
            )
            continue

        known_options = commands[
            command_id
        ].get(
            "options",
            {},
        )

        invalid_options = [
            option
            for option in options
            if option not in known_options
        ]

        if invalid_options:

            print(
                f"\n[Analyzer] Rejected invalid option(s) "
                f"for '{command_id}': "
                f"{invalid_options}"
            )

            continue

        valid_next_actions.append(
            {
                "command_id": command_id,
                "options": options,
                "reason": reason,
            }
        )

    analysis["next_actions"] = valid_next_actions

    return analysis


def analyze_results(
    user_request: str,
    execution_results: list[dict],
) -> dict:
    """
    Send executor results to the SLM and return
    a validated analysis.
    """

    if not isinstance(
        user_request,
        str,
    ):
        raise ValueError(
            "user_request must be a string."
        )

    if not isinstance(
        execution_results,
        list,
    ):
        raise ValueError(
            "execution_results must be a list."
        )

    prompt = build_analysis_prompt(
        user_request,
        execution_results,
    )

    raw_response = ask(prompt)

    try:
        analysis = json.loads(
            raw_response
        )

    except json.JSONDecodeError as error:

        raise ValueError(
            "SLM Analyzer returned invalid JSON:\n"
            f"{raw_response}"
        ) from error

    return validate_analysis(
        analysis
    )
