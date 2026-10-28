"""Client for the local Ollama Small Language Model (SLM).

Ensures strictly offline operation, configurable models, robust JSON extraction,
and helpful diagnostic error reporting when Ollama is unavailable.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Optional

from .config import (
    DEFAULT_MODEL,
    LLM_TIMEOUT_SECONDS,
    OLLAMA_GENERATE_URL,
    OLLAMA_TAGS_URL,
)


def extract_json_from_text(text: str) -> Any:
    """
    Robustly extract and parse a JSON object or array from LLM response text.

    Handles raw JSON, markdown code fences (```json ... ```), preamble text,
    and trailing commentary.
    """
    if not isinstance(text, str):
        raise ValueError("Input text must be a string.")

    cleaned = text.strip()

    # 1. Direct parse attempt
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. Markdown fence extraction (```json ... ``` or ``` ... ```)
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    fence_matches = re.findall(fence_pattern, cleaned, re.IGNORECASE)
    for candidate in fence_matches:
        candidate_stripped = candidate.strip()
        try:
            return json.loads(candidate_stripped)
        except json.JSONDecodeError:
            continue

    # 3. Outermost curly bracket extraction for JSON objects: { ... }
    start_brace = cleaned.find("{")
    end_brace = cleaned.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        candidate_obj = cleaned[start_brace : end_brace + 1]
        try:
            return json.loads(candidate_obj)
        except json.JSONDecodeError:
            pass

    # 4. Outermost square bracket extraction for JSON arrays: [ ... ]
    start_bracket = cleaned.find("[")
    end_bracket = cleaned.rfind("]")
    if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
        candidate_arr = cleaned[start_bracket : end_bracket + 1]
        try:
            return json.loads(candidate_arr)
        except json.JSONDecodeError:
            pass

    # If all extraction strategies fail, raise JSONDecodeError on original text
    return json.loads(cleaned)


def check_ollama(
    model: Optional[str] = None,
    timeout: int = 3,
) -> tuple[bool, str]:
    """
    Check if the local Ollama server is running and the specified model is installed.

    Returns:
        (is_ready, message)
    """
    target_model = model or DEFAULT_MODEL

    req = urllib.request.Request(
        OLLAMA_TAGS_URL,
        headers={"Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        return (
            False,
            (
                f"Could not connect to local Ollama server at {OLLAMA_TAGS_URL}: {error}.\n"
                "Troubleshooting steps:\n"
                "  1. Ensure Ollama is installed (https://ollama.ai).\n"
                "  2. Start the service: 'ollama serve' or 'systemctl start ollama'.\n"
                f"  3. Ensure the model is downloaded: 'ollama pull {target_model}'."
            ),
        )
    except Exception as error:
        return (
            False,
            f"Unexpected error communicating with Ollama: {error}",
        )

    # Check model presence in tags
    models = data.get("models", [])
    installed_names: list[str] = []
    for m in models:
        name = m.get("name", "")
        installed_names.append(name)
        if name == target_model or name.startswith(f"{target_model}:"):
            return (
                True,
                f"Ollama is reachable and model '{target_model}' is installed.",
            )

    return (
        False,
        (
            f"Ollama is running, but model '{target_model}' was not found.\n"
            f"Installed models: {', '.join(installed_names) if installed_names else 'none'}.\n"
            f"To install, run: ollama pull {target_model}"
        ),
    )


def ask(
    prompt: str,
    model: Optional[str] = None,
    format_json: bool = True,
    timeout: Optional[int] = None,
) -> str:
    """
    Send a prompt to the local Ollama SLM and return the raw text response.

    Strictly communicates with the configured local endpoint (offline-only).
    """
    target_model = model or DEFAULT_MODEL
    req_timeout = timeout or LLM_TIMEOUT_SECONDS

    # Security check: ensure endpoint is local (loopback)
    if "127.0.0.1" not in OLLAMA_GENERATE_URL and "localhost" not in OLLAMA_GENERATE_URL:
        raise RuntimeError(
            "LocalOps policy violation: Ollama URL must target local loopback (127.0.0.1/localhost)."
        )

    payload: dict[str, Any] = {
        "model": target_model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "num_predict": 600,
        },
    }

    if format_json:
        payload["format"] = "json"

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=req_timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to Ollama at {OLLAMA_GENERATE_URL}: {error}.\n"
            "Ensure Ollama is running ('ollama serve') and accessible offline."
        ) from error
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Ollama returned invalid HTTP JSON response."
        ) from error

    response_text = result.get("response")

    if not isinstance(response_text, str):
        raise RuntimeError(
            "Ollama response does not contain valid text."
        )

    return response_text.strip()
