from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.llm import ask


def main():
    response = ask(
        "Return only this sentence: Ollama is working."
    )

    print(response)


if __name__ == "__main__":
    main()
