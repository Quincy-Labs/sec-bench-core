"""Anthropic API adapter. Needs ANTHROPIC_API_KEY."""

from __future__ import annotations

import os
import time

import anthropic

from .base import Completion

# USD per 1K tokens: (prompt, completion). Fill in current prices for the
# models you run; anything absent reports cost_usd = None.
PRICING: dict[str, tuple[float, float]] = {}


class AnthropicAdapter:
    def __init__(self, model: str):
        self.model = model
        self.client = anthropic.Anthropic()

    def complete(
        self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 8192
    ) -> Completion:
        max_tokens = int(os.environ.get("ANTHROPIC_MAX_TOKENS", max_tokens))
        t0 = time.monotonic()
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            latency = time.monotonic() - t0
        except Exception as e:
            return Completion("", time.monotonic() - t0, error=f"{type(e).__name__}: {e}")
        text = "".join(b.text for b in msg.content if b.type == "text")
        usage = msg.usage
        cost = None
        price = PRICING.get(self.model)
        if price:
            cost = (price[0] * (usage.input_tokens or 0) + price[1] * (usage.output_tokens or 0)) / 1000
        return Completion(text, latency, usage.input_tokens, usage.output_tokens, cost_usd=cost)
