from .agent import run_agent


def main():
    request = input(
        "LocalOps> "
    ).strip()

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
