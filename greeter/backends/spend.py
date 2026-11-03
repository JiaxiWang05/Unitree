"""Spend guard: adds up ``response.done`` usage and logs the running and hourly cost."""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Deque, Dict, Optional, Tuple

log = logging.getLogger(__name__)

# USD per 1M tokens (developers.openai.com model pages, checked 2026-10-16)
PRICES: Dict[str, Dict[str, float]] = {
    "gpt-realtime-2.1": {"text_in": 4.0, "audio_in": 32.0, "image_in": 5.0, "cached_in": 0.40, "text_out": 24.0, "audio_out": 64.0},
}

# error codes / messages that mean "this provider is done for today"
DOWN_MARKERS = ("spend_limit", "insufficient_quota", "billing", "quota_exceeded", "invalid_api_key", "account_deactivated")


def is_provider_down(code: Optional[str], message: Optional[str]) -> bool:
    text = ("%s %s" % (code or "", message or "")).lower()
    return any(marker in text for marker in DOWN_MARKERS)


def response_cost(model: str, usage: dict) -> Optional[float]:
    """Cost of one response from its ``usage`` block; None when the model's prices are unknown."""
    price = PRICES.get(model)
    if price is None or not usage:
        return None
    inp = usage.get("input_token_details") or {}
    out = usage.get("output_token_details") or {}
    cached = inp.get("cached_tokens") or 0
    text_in = max(0, (inp.get("text_tokens") or 0) - (inp.get("cached_tokens_details") or {}).get("text_tokens", 0))
    audio_in = max(0, (inp.get("audio_tokens") or 0) - (inp.get("cached_tokens_details") or {}).get("audio_tokens", 0))
    image_in = max(0, (inp.get("image_tokens") or 0) - (inp.get("cached_tokens_details") or {}).get("image_tokens", 0))
    if not inp and usage.get("input_tokens"):
        audio_in = usage["input_tokens"]  # no breakdown: assume the dearer kind
    cost = (
        text_in * price["text_in"]
        + audio_in * price["audio_in"]
        + image_in * price["image_in"]
        + cached * price["cached_in"]
        + (out.get("text_tokens") or 0) * price["text_out"]
        + (out.get("audio_tokens") or (0 if out else usage.get("output_tokens") or 0)) * price["audio_out"]
    )
    return cost / 1e6


class SpendMeter:
    """Process-wide running total; one instance shared by every session."""

    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.total_usd = 0.0
        self._recent: Deque[Tuple[float, float]] = deque()

    def add(self, cost: Optional[float]) -> None:
        if not cost:
            return
        now = self.clock()
        self.total_usd += cost
        self._recent.append((now, cost))
        while self._recent and now - self._recent[0][0] > 3600:
            self._recent.popleft()

    def last_hour_usd(self) -> float:
        now = self.clock()
        return sum(c for t, c in self._recent if now - t <= 3600)


METER = SpendMeter()
