"""
wrappers/anthropic.py — Transparent proxy for anthropic.Anthropic / anthropic.AsyncAnthropic.

Intercepts messages.create() to record token counts, latency, and cost.
Every other attribute passes through to the underlying client unchanged.
"""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import TokenLens


def _first_user_text(messages: list) -> str | None:
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            return content[:500] or None
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    return text[:500] or None
    return None


# ── Sync wrappers ──────────────────────────────────────────────────────────────

class _WrappedMessages:
    def __init__(self, messages: Any, tl: "TokenLens") -> None:
        self._m = messages
        self._tl = tl

    def create(self, **kwargs) -> Any:
        t0 = time.perf_counter()
        response = self._m.create(**kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000
        usage = getattr(response, "usage", None)
        if usage:
            self._tl._log_background(
                model=kwargs.get("model", "unknown"),
                tokens_in=getattr(usage, "input_tokens", 0) or 0,
                tokens_out=getattr(usage, "output_tokens", 0) or 0,
                latency_ms=latency_ms,
                query_text=_first_user_text(kwargs.get("messages", [])),
            )
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._m, name)


class WrappedAnthropic:
    """Transparent proxy for anthropic.Anthropic."""

    def __init__(self, client: Any, tl: "TokenLens") -> None:
        self._client = client
        self._tl = tl
        self.messages = _WrappedMessages(client.messages, tl)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


# ── Async wrappers ─────────────────────────────────────────────────────────────

class _AsyncWrappedMessages:
    def __init__(self, messages: Any, tl: "TokenLens") -> None:
        self._m = messages
        self._tl = tl

    async def create(self, **kwargs) -> Any:
        t0 = time.perf_counter()
        response = await self._m.create(**kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000
        usage = getattr(response, "usage", None)
        if usage:
            payload = self._tl._build_payload(
                kwargs.get("model", "unknown"),
                getattr(usage, "input_tokens", 0) or 0,
                getattr(usage, "output_tokens", 0) or 0,
                latency_ms,
                _first_user_text(kwargs.get("messages", [])),
                None,
            )
            asyncio.get_event_loop().create_task(self._tl._send_async(payload))
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._m, name)


class AsyncWrappedAnthropic:
    """Transparent proxy for anthropic.AsyncAnthropic."""

    def __init__(self, client: Any, tl: "TokenLens") -> None:
        self._client = client
        self._tl = tl
        self.messages = _AsyncWrappedMessages(client.messages, tl)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


# ── Factory ────────────────────────────────────────────────────────────────────

def wrap_anthropic(client: Any, tl: "TokenLens") -> Any:
    """Return an AsyncWrappedAnthropic for async clients, WrappedAnthropic otherwise."""
    try:
        from anthropic import AsyncAnthropic
        if isinstance(client, AsyncAnthropic):
            return AsyncWrappedAnthropic(client, tl)
    except ImportError:
        pass
    return WrappedAnthropic(client, tl)
