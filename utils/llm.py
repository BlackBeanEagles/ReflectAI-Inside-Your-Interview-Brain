"""
LLM utility module.
Responsibility: Talk to Ollama and return a response string.

Uses Ollama's HTTP API (http://localhost:11434) instead of subprocess
to avoid terminal escape sequences and subprocess conflicts.

Isolated from the API layer so models can be swapped (Llama3 → OpenAI → Claude)
without touching any route logic.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:latest"   # Switch to llama3.1:8b after reboot (GPU mode)


def call_llm(prompt: str) -> str:
    """
    Sends a prompt to the Ollama model via HTTP API.
    Returns the generated text as a string.
    Handles errors gracefully — never crashes the API.
    """
    try:
        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=180)

        if response.status_code != 200:
            return f"LLM error: Ollama returned status {response.status_code} — {response.text[:200]}"

        data = response.json()
        result = data.get("response", "").strip()

        if not result:
            return "LLM returned an empty response. Try again."

        return result

    except requests.exceptions.ConnectionError:
        return "Ollama is not running. Start it with: .\\start_ollama.bat"
    except requests.exceptions.Timeout:
        return "LLM request timed out after 180 seconds."
    except Exception as e:
        return f"Unexpected error calling LLM: {str(e)}"
