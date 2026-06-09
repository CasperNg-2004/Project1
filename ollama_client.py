"""
ollama_client.py — Ollama streaming chat client

Streams responses from a local Ollama instance.
"""

import json
import logging
import requests
from typing import Generator

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_PATH = "/api/chat"
OLLAMA_TAGS_PATH = "/api/tags"
OLLAMA_URL = OLLAMA_BASE_URL + OLLAMA_CHAT_PATH


class OllamaClient:
    def __init__(self, model: str = "llama3", base_url: str = OLLAMA_URL,
                 gpu_layers: int = 99):
        self.model      = model
        self.base_url   = base_url
        self.gpu_layers = gpu_layers   # 99 = offload all layers to GPU
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
        tags_url = self.base_url.replace(OLLAMA_CHAT_PATH, OLLAMA_TAGS_PATH)
        try:
            r = requests.get(tags_url, timeout=5)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            logger.exception("Failed to fetch Ollama model list")
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
            "options": {
                "num_gpu": self.gpu_layers,   # offload layers to GPU (0 = CPU only)
            },
        }

        full_response = ""
        error_occurred = False
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
            error_occurred = True
            # Roll back the user message to keep history consistent
            if self._history and self._history[-1]["role"] == "user":
                self._history.pop()
            yield "[Error: Cannot connect to Ollama. Is it running? Try: ollama serve]"
        except Exception as e:
            error_occurred = True
            logger.exception("Unexpected error during Ollama stream")
            if self._history and self._history[-1]["role"] == "user":
                self._history.pop()
            yield f"[Error: {e}]"

        if full_response and not error_occurred:
            self._history.append({"role": "assistant", "content": full_response})