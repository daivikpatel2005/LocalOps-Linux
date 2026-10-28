def confirm_plan(commands: list[dict]) -> bool:
    """
    Ask the user for explicit permission before executing
    a validated troubleshooting plan.
    """

    if not isinstance(commands, list):
        raise ValueError("Commands must be a list.")

    if not commands:
        raise ValueError("No commands to confirm.")

    print()
    print("=" * 60)
    print("LocalOps wants to run the following commands:")
    print("=" * 60)

    for index, command in enumerate(commands, 1):
        print(f"\n[{index}] ${command['command']}")

        purpose = command.get("purpose", "")
        risk = command.get("risk", "unknown")

        if purpose:
            print(f"    Purpose : {purpose}")

        print(f"    Risk    : {risk}")

    print()
    print("=" * 60)

    answer = input(
        "Allow these commands to run? [y/N]: "
    ).strip().lower()

    return answer in ("y", "yes")
