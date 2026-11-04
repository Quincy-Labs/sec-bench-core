"""Adapter result type shared by all model adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Completion:
    text: str
    latency_s: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    error: str | None = None
    reasoning: str | None = None  # message.reasoning_content (thinking models); stored for diagnosis

    def as_record(self) -> dict:
        """Per-output metadata stored in results files."""
        return {
            "raw": self.text,
            "latency_s": round(self.latency_s, 2),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": self.cost_usd,
            "error": self.error,
            "reasoning": self.reasoning,
        }
