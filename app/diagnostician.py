"""Diagnostic engine of LocalOps (legacy/alternative interface).

Analyzes command results using the local SLM.
"""

from __future__ import annotations

import json
from typing import Any

from .llm import ask, extract_json_from_text

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

Allowed status values: "problem_found", "no_problem_found", "needs_more_data", "command_failed"
Allowed severity values: "low", "medium", "high", "critical", "unknown"
"""


def diagnose(user_request: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "user_request": user_request,
        "command_results": results,
    }

    prompt = f"""
{DIAGNOSIS_PROMPT}

INPUT:
{json.dumps(payload, indent=2)}

Analyze the command results.
"""
    try:
        response = ask(prompt).strip()
        return extract_json_from_text(response)
    except Exception as error:
        return {
            "status": "needs_more_data",
            "diagnosis": f"Automated analysis unavailable: {error}",
            "evidence": [f"Captured {len(results)} command result(s)"],
            "severity": "unknown",
            "next_step": "Inspect command outputs directly or start local Ollama server",
            "needs_more_data": True,
        }
