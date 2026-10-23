import json
import urllib.request
import urllib.error


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3:1.7b"


def ask(prompt: str) -> str:
    """
    Send a prompt to the local Ollama SLM and return its response.

    The SLM is used for reasoning/planning.
    It does NOT execute Linux commands.
    """

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 500,
        },
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to Ollama: {error}"
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Ollama returned invalid response data."
        ) from error

    response_text = result.get("response")

    if not isinstance(response_text, str):
        raise RuntimeError(
            "Ollama response does not contain valid text."
        )

    return response_text.strip()
