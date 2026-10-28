"""Planner module for LocalOps.

Generates a structured diagnostic plan using the local SLM and knowledge base.
Provides robust schema validation, bounded retries on structural errors,
and deterministic workflow planning for supported Linux troubleshooting scenarios.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .config import DEFAULT_MODEL, MAX_PLANNER_RETRIES
from .knowledge import (
    build_context,
    find_workflow,
    get_command,
    get_supported_troubleshooting_areas,
    get_workflow,
)
from .llm import ask, extract_json_from_text


class PlannerError(ValueError):
    """Raised when the planner cannot produce a valid diagnostic plan."""
    pass


SYSTEM_PROMPT = """
You are the planning engine for LocalOps, an offline Linux troubleshooting agent.

Your job is to analyze the user's problem and create a safe diagnostic plan
using ONLY commands from the provided knowledge base.

RULES:
1. Return a JSON object with EXACTLY these four required top-level fields:
   - "problem": (string) short description of the problem
   - "assessment": (string) brief explanation of the initial diagnostic approach
   - "workflow_id": (string or null) the matched workflow ID if applicable
   - "plan": (array of objects) the diagnostic commands to execute
2. "plan" MUST ALWAYS be a JSON array of objects. NEVER return a string or an object for "plan".
3. Each object in "plan" MUST contain:
   - "command_id": (string) matching an allowed command in the knowledge base
   - "options": (array of strings) allowed options from the knowledge base, or []
   - "purpose": (string) why this command is being run
4. NEVER invent commands or command IDs.
5. NEVER suggest destructive commands, package removal, service restart, or reboot.
6. NEVER suggest shell pipelines (|), redirections (>), or command chaining (&&, ;).
7. Return ONLY valid JSON. Do not include markdown code fences or conversational text.
"""


def _validate_raw_plan_dict(plan_dict: Any, user_request: str) -> dict[str, Any]:
    """
    Validate the structure of a planner response dictionary.

    Raises PlannerError with actionable feedback if invalid.
    """
    if not isinstance(plan_dict, dict):
        raise PlannerError(
            f"Planner response must be a JSON object, got {type(plan_dict).__name__}."
        )

    required_fields = ["problem", "assessment", "workflow_id", "plan"]
    missing = [f for f in required_fields if f not in plan_dict]
    if missing:
        raise PlannerError(
            f"Planner response missing required field(s): {', '.join(missing)}."
        )

    if not isinstance(plan_dict["problem"], str) or not plan_dict["problem"].strip():
        raise PlannerError("Planner field 'problem' must be a non-empty string.")

    if not isinstance(plan_dict["assessment"], str):
        raise PlannerError("Planner field 'assessment' must be a string.")

    # Normalize "null" string to None
    wf_id = plan_dict.get("workflow_id")
    if wf_id == "null" or wf_id == "":
        plan_dict["workflow_id"] = None
    elif wf_id is not None and not isinstance(wf_id, str):
        raise PlannerError("Planner field 'workflow_id' must be a string or null.")

    # Plan MUST be a list
    raw_plan = plan_dict.get("plan")
    if not isinstance(raw_plan, list):
        raise PlannerError(
            f"Planner field 'plan' must be a list, got {type(raw_plan).__name__}."
        )

    if not raw_plan:
        raise PlannerError("SLM planner returned an empty diagnostic plan.")

    for index, item in enumerate(raw_plan, 1):
        if not isinstance(item, dict):
            raise PlannerError(
                f"Plan item {index} must be an object, got {type(item).__name__}."
            )
        cid = item.get("command_id")
        if not isinstance(cid, str) or not cid.strip():
            raise PlannerError(f"Plan item {index} missing valid 'command_id'.")
        opts = item.get("options")
        if opts is None or not isinstance(opts, list):
            raise PlannerError(f"Plan item {index} ('{cid}') 'options' must be a list.")
        purpose = item.get("purpose")
        if purpose is not None and not isinstance(purpose, str):
            raise PlannerError(f"Plan item {index} ('{cid}') 'purpose' must be a string.")

    return plan_dict


def build_deterministic_plan(
    user_request: str,
    workflow_id: str,
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a deterministic diagnostic plan directly from a matched workflow.

    Provides instant, zero-latency planning without LLM parsing failures.
    """
    candidates = workflow.get("candidate_commands", [])
    plan_items = []
    for cand in candidates:
        cid = cand.get("command_id")
        opts = cand.get("options", [])
        cmd_meta = get_command(cid) or {}
        desc = cmd_meta.get("description", f"Run {cid}")
        plan_items.append(
            {
                "command_id": cid,
                "options": list(opts),
                "purpose": desc,
            }
        )

    if not plan_items:
        raise PlannerError(
            f"Workflow '{workflow_id}' contains no valid candidate commands."
        )

    return {
        "problem": user_request,
        "assessment": f"Diagnosing {workflow.get('description', workflow_id)}.",
        "workflow_id": workflow_id,
        "plan": plan_items,
    }


def create_plan(
    user_request: str,
    model: Optional[str] = None,
    use_deterministic_workflow: bool = False,
) -> dict[str, Any]:
    """
    Create a troubleshooting plan for the user request.

    If use_deterministic_workflow is True and a known workflow matches,
    returns an immediate safe plan directly from the knowledge base.
    Otherwise, invokes the local SLM with the matched context and performs
    bounded error-correction retries if the SLM returns a malformed structure.
    """
    if not isinstance(user_request, str):
        raise ValueError("User request must be a string.")

    cleaned_request = user_request.strip()
    if not cleaned_request:
        raise ValueError("User request cannot be empty.")

    workflow_id, workflow = find_workflow(cleaned_request)

    # If requested or if deterministic path is preferred, use the workflow directly
    if use_deterministic_workflow and workflow_id and workflow:
        return build_deterministic_plan(cleaned_request, workflow_id, workflow)

    context_json = build_context(workflow_id)

    prompt = f"""
{SYSTEM_PROMPT}

KNOWLEDGE BASE CONTEXT:
{context_json}

MATCHED WORKFLOW:
{workflow_id or "None"}

USER REQUEST:
{cleaned_request}

Create the complete first diagnostic plan.
Return ONLY the JSON object.
""".strip()

    target_model = model or DEFAULT_MODEL
    last_error: Optional[Exception] = None

    for attempt in range(MAX_PLANNER_RETRIES + 1):
        try:
            raw_response = ask(prompt, model=target_model)
            parsed_data = extract_json_from_text(raw_response)
            validated_plan = _validate_raw_plan_dict(parsed_data, cleaned_request)

            # Pre-validate against the security validator rules directly in planning loop
            from .validator import validate_plan
            validate_plan(validated_plan)
            return validated_plan

        except Exception as error:
            last_error = error

            # If we matched a workflow and LLM fails or produces an invalid plan,
            # fallback cleanly to the deterministic workflow plan!
            if workflow_id and workflow:
                if attempt >= MAX_PLANNER_RETRIES or "connect" in str(error).lower():
                    return build_deterministic_plan(
                        cleaned_request, workflow_id, workflow
                    )

            if attempt < MAX_PLANNER_RETRIES:
                candidate_examples = []
                if workflow:
                    for c in workflow.get("candidate_commands", []):
                        cid = c.get("command_id", "")
                        opts = c.get("options", [])
                        candidate_examples.append(cid + (" " + " ".join(opts) if opts else ""))

                # Bounded retry with error correction prompt
                prompt = f"""
{SYSTEM_PROMPT}

Your previous response was rejected due to this error:
{error}

USER REQUEST:
{cleaned_request}

MATCHED WORKFLOW: {workflow_id}
ALLOWED CANDIDATE COMMANDS FOR THIS WORKFLOW:
{candidate_examples}

Return ONLY a valid JSON object with 'problem', 'assessment', 'workflow_id', and 'plan'.
Ensure 'plan' is a non-empty JSON ARRAY of objects matching the allowed commands and options.
""".strip()

    # If no workflow was matched and LLM planning failed:
    if not workflow_id:
        areas = "\n".join(get_supported_troubleshooting_areas()[:8])
        raise PlannerError(
            f"Planner error: {last_error}\n\n"
            "LocalOps could not plan diagnostics for this request.\n"
            f"Supported troubleshooting areas include:\n{areas}"
        )

    raise PlannerError(f"Planner error: {last_error}")
