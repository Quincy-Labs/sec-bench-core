"""Local models through oMLX's OpenAI-compatible server.

Start the multi-model server with `omlx start` (default http://127.0.0.1:8001),
or pin one model with `omlx serve <hf-repo> --port 8001`.
The API key defaults to `auth.api_key` in `~/.omlx/settings.json`;
override with the OMLX_API_KEY environment variable.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from .base import Completion


def default_api_key() -> str:
    env = os.environ.get("OMLX_API_KEY", "")
    if env:
        return env
    try:
        settings = json.loads((Path.home() / ".omlx" / "settings.json").read_text())
        return settings.get("auth", {}).get("api_key", "")
    except (OSError, json.JSONDecodeError):
        return ""


class OmlxAdapter:
    def __init__(self, model: str, base_url: str | None = None, thinking: bool | None = None):
        self.model = model
        self.base_url = (base_url or os.environ.get("OMLX_URL", "http://127.0.0.1:8001/v1")).rstrip("/")
        self.api_key = default_api_key()
        self.thinking = thinking  # None = server default

    def complete_conversation(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 16384
    ) -> Completion:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if self.thinking is not None:
            # Pin reasoning on/off: thinking models otherwise spend the whole
            # token budget on reasoning and return empty content.
            body["thinking"] = self.thinking
            body["chat_template_kwargs"] = {"enable_thinking": self.thinking}
        t0 = time.monotonic()
        try:
            r = requests.post(self.base_url + "/chat/completions", headers=headers, json=body, timeout=3600)
            latency = time.monotonic() - t0
            if r.status_code != 200:
                return Completion("", latency, error=f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()
        except requests.RequestException as e:
            return Completion("", time.monotonic() - t0, error=f"{type(e).__name__}: {e}")
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        text = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or None
        usage = data.get("usage") or {}
        return Completion(
            text,
            latency,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            cost_usd=0.0,
            reasoning=reasoning,
        )

    def complete(
        self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 16384
    ) -> Completion:
        return self.complete_conversation(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
