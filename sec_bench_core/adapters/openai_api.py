"""OpenAI API adapter. Needs OPENAI_API_KEY (optionally OPENAI_BASE_URL)."""

from __future__ import annotations

import os
import time

from openai import OpenAI

from .base import Completion

# USD per 1M tokens: (prompt, completion). Fill in current prices for the
# models you run; anything absent reports cost_usd = None.
PRICING: dict[str, tuple[float, float]] = {}


class OpenAIAdapter:
    def __init__(self, model: str):
        self.model = model
        self.client = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL") or None)

    def complete(
        self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 16384
    ) -> Completion:
        t0 = time.monotonic()
        try:
            r = self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            latency = time.monotonic() - t0
        except Exception as e:  # openai raises a generic APIError hierarchy
            return Completion("", time.monotonic() - t0, error=f"{type(e).__name__}: {e}")
        text = r.choices[0].message.content or "" if r.choices else ""
        usage = r.usage
        cost = None
        price = PRICING.get(self.model)
        if price and usage:
            cost = (
                price[0] * (usage.prompt_tokens or 0) + price[1] * (usage.completion_tokens or 0)
            ) / 1_000_000
        return Completion(
            text,
            latency,
            usage.prompt_tokens if usage else None,
            usage.completion_tokens if usage else None,
            cost_usd=cost,
        )
