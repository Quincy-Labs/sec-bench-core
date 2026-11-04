"""Local models through Ollama's HTTP API. Keep for machines that use Ollama
instead of oMLX. Start Ollama first: `ollama serve`.
"""

from __future__ import annotations

import os
import time

import requests

from .base import Completion


class OllamaAdapter:
    def __init__(self, model: str, base_url: str | None = None):
        self.model = model
        self.url = (base_url or os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")).rstrip("/")

    def complete(
        self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 8192
    ) -> Completion:
        body = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        t0 = time.monotonic()
        try:
            r = requests.post(self.url, json=body, timeout=3600)
            latency = time.monotonic() - t0
            if r.status_code != 200:
                return Completion("", latency, error=f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()
        except requests.RequestException as e:
            return Completion("", time.monotonic() - t0, error=f"{type(e).__name__}: {e}")
        text = data.get("message", {}).get("content") or ""
        return Completion(text, latency, data.get("prompt_eval_count"), data.get("eval_count"), cost_usd=0.0)
