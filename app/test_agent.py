from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.agent import run_agent


def main():
    if len(sys.argv) > 1:
        request = " ".join(sys.argv[1:]).strip()
    elif not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        request = piped if piped else "Why is my RAM full?"
    else:
        try:
            request = input("LocalOps> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

    if not request:
        print("No request provided.")
        return

    try:
        run_agent(request)

    except KeyboardInterrupt:
        print("\n\nLocalOps stopped.")

    except Exception as error:
        print(
            "\nLOCALOPS ERROR"
        )
        print(
            type(error).__name__,
            ":",
            error
        )


if __name__ == "__main__":
    main()
