"""Ollama generation adapter for local answer generation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import urllib.request


class GenerationClient:
    """Protocol-like base for generation clients."""

    model_name: str

    def generate(self, prompt: str) -> str:
        raise NotImplementedError


@dataclass
class OllamaGenerationClient(GenerationClient):
    """Minimal Ollama /api/generate client."""

    model_name: str = "qwen2.5-coder:7b"
    endpoint: str = "http://127.0.0.1:11434"
    timeout_seconds: int = 120

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }
        request = urllib.request.Request(
            f"{self.endpoint.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return str(body.get("response", "")).strip()
