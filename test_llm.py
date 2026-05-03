import subprocess

def test_llm():
    prompt = "Ask one HR interview question"

    result = subprocess.run(
        ["ollama", "run", "llama3"],
        input=prompt.encode(),
        stdout=subprocess.PIPE
    )

    print(result.stdout.decode())

if __name__ == "__main__":
    test_llm()