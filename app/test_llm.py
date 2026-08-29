from .llm import ask


def main():
    response = ask(
        "Return only this sentence: Ollama is working."
    )

    print(response)


if __name__ == "__main__":
    main()
