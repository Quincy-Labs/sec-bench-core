"""Model adapters. Each adapter exposes complete(system, user) -> Completion.

Specs: omlx:<model> (local:<model> is an alias), lmstudio:<model>,
ollama:<model>, openai:<model>, anthropic:<model>.
"""

from __future__ import annotations

from .base import Completion  # noqa: F401


def get_adapter(spec: str):
    provider, _, model = spec.partition(":")
    if provider in ("local", "omlx"):
        from .omlx import OmlxAdapter

        return OmlxAdapter(model)
    if provider in ("lmstudio", "lm_studio"):
        from .lmstudio import LmStudioAdapter

        return LmStudioAdapter(model)
    if provider == "ollama":
        from .ollama import OllamaAdapter

        return OllamaAdapter(model)
    if provider == "openai":
        from .openai_api import OpenAIAdapter

        return OpenAIAdapter(model)
    if provider == "anthropic":
        from .anthropic_api import AnthropicAdapter

        return AnthropicAdapter(model)
    raise ValueError(
        "unknown provider: "
        f"{provider} (want omlx/local, lmstudio, ollama, openai, or anthropic)"
    )
