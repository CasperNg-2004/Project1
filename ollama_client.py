"""
ollama_client.py — Ollama streaming chat client

Streams responses from a local Ollama instance.
"""

import json
import requests
from typing import Generator


OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3"


class OllamaClient:
    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_URL):
        self.model = model
        self.base_url = base_url
        self._history: list[dict] = []
        self._system_prompt = (
            "You are a helpful voice assistant. "
            "Keep your answers concise and conversational — "
            "ideally one to three sentences unless more detail is truly needed."
        )

    def set_model(self, model: str):
        self.model = model

    def set_system_prompt(self, prompt: str):
        self._system_prompt = prompt

    def clear_history(self):
        self._history.clear()

    def list_local_models(self) -> list[str]:
        """Return names of models available in the local Ollama instance."""
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def stream_chat(self, user_message: str) -> Generator[str, None, None]:
        """
        Send user_message, yield response token-by-token.
        Appends both turns to conversation history.
        """
        self._history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": self._system_prompt}] + self._history

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        full_response = ""
        try:
            with requests.post(self.base_url, json=payload, stream=True, timeout=60) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_response += token
                        yield token
                    if chunk.get("done"):
                        break
        except requests.exceptions.ConnectionError:
            yield "[Error: Cannot connect to Ollama. Is it running? Try: ollama serve]"
        except Exception as e:
            yield f"[Error: {e}]"

        if full_response:
            self._history.append({"role": "assistant", "content": full_response})