import json

from .llm import ask


DIAGNOSIS_PROMPT = """
You are the diagnostic engine of LocalOps, an offline Linux troubleshooting agent.

You receive:
1. The user's original problem.
2. Commands that were executed.
3. Their actual Linux output.

Analyze the evidence and determine what is likely happening.

IMPORTANT RULES:

1. Use only the evidence provided.
2. Do not invent system information.
3. Do not invent command output.
4. Do not execute commands.
5. Do not provide long explanations.
6. If the evidence is insufficient, say so.
7. If another investigation is needed, identify what information is needed.
8. Keep the response concise.
9. Return ONLY valid JSON.
10. Do not use markdown.
11. Do not use code fences.

Return exactly:

{
  "status": "problem_found",
  "diagnosis": "short diagnosis",
  "evidence": [
    "short evidence point"
  ],
  "severity": "low",
  "next_step": "short next step",
  "needs_more_data": false
}

Allowed status values:

"problem_found"
"no_problem_found"
"needs_more_data"
"command_failed"

Allowed severity values:

"low"
"medium"
"high"
"critical"
"unknown"
"""


def diagnose(user_request, results):
    payload = {
        "user_request": user_request,
        "command_results": results
    }

    prompt = f"""
{DIAGNOSIS_PROMPT}

INPUT:

{json.dumps(payload, indent=2)}

Analyze the command results.
"""

    response = ask(prompt).strip()

    if response.startswith("```"):
        lines = response.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        response = "\n".join(lines).strip()

    try:
        return json.loads(response)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "SLM returned invalid diagnosis JSON:\n\n"
            + response
        ) from error
