from .executor import execute_command


def main():
    print("LocalOps Executor Test")
    print()

    result = execute_command(
        "uptime"
    )

    print("Command:")
    print(result["command"])

    print("\nExit code:")
    print(result["return_code"])

    print("\nOutput:")
    print(result["stdout"])

    if result["stderr"]:
        print("\nError:")
        print(result["stderr"])

    print(
        f"\nExecution time: "
        f"{result['duration_seconds']} seconds"
    )


if __name__ == "__main__":
    main()
