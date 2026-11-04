"""Local models through the LM Studio server (OpenAI-compatible).

LM Studio's local server defaults to http://127.0.0.1:1234/v1 and needs no
API key (any bearer token is accepted). Override the URL with LMSTUDIO_URL.
"""

from __future__ import annotations

import os

from .omlx import OmlxAdapter


class LmStudioAdapter(OmlxAdapter):
    def __init__(self, model: str, base_url: str | None = None, thinking: bool | None = None):
        super().__init__(
            model,
            base_url=base_url or os.environ.get("LMSTUDIO_URL", "http://127.0.0.1:1234/v1"),
            thinking=thinking,
        )
        self.api_key = os.environ.get("LMSTUDIO_API_KEY", "lm-studio")
