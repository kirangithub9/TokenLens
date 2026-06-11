"""
wrappers/openai.py — Transparent proxy for openai.OpenAI / openai.AsyncOpenAI.

Intercepts chat.completions.create() to record token counts, latency, and cost.
Every other attribute passes through to the underlying client unchanged.
"""
from __future__ import annotations

PROVIDER_MODULE = "openai"

import asyncio
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import TokenLens


def _first_user_text(messages: list) -> str | None:
    """Return the text of the first user message, or None."""
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

class _WrappedCompletions:
    def __init__(self, completions: Any, tl: "TokenLens") -> None:
        self._c = completions
        self._tl = tl

    def create(self, **kwargs) -> Any:
        t0 = time.perf_counter()
        response = self._c.create(**kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000
        usage = getattr(response, "usage", None)
        if usage:
            choices = getattr(response, "choices", [])
            response_text = choices[0].message.content if choices else None
            self._tl._log_background(
                model=kwargs.get("model", "unknown"),
                tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
                tokens_out=getattr(usage, "completion_tokens", 0) or 0,
                latency_ms=latency_ms,
                query_text=_first_user_text(kwargs.get("messages", [])),
                response_text=response_text,
            )
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._c, name)


class _WrappedChat:
    def __init__(self, chat: Any, tl: "TokenLens") -> None:
        self._chat = chat
        self.completions = _WrappedCompletions(chat.completions, tl)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class WrappedOpenAI:
    """Transparent proxy for openai.OpenAI."""

    def __init__(self, client: Any, tl: "TokenLens") -> None:
        self._client = client
        self._tl = tl
        self.chat = _WrappedChat(client.chat, tl)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


# ── Async wrappers ─────────────────────────────────────────────────────────────

class _AsyncWrappedCompletions:
    def __init__(self, completions: Any, tl: "TokenLens") -> None:
        self._c = completions
        self._tl = tl

    async def create(self, **kwargs) -> Any:
        t0 = time.perf_counter()
        response = await self._c.create(**kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000
        usage = getattr(response, "usage", None)
        if usage:
            choices = getattr(response, "choices", [])
            response_text = choices[0].message.content if choices else None
            payload = self._tl._build_payload(
                kwargs.get("model", "unknown"),
                getattr(usage, "prompt_tokens", 0) or 0,
                getattr(usage, "completion_tokens", 0) or 0,
                latency_ms,
                _first_user_text(kwargs.get("messages", [])),
                None,
                response_text,
            )
            asyncio.get_event_loop().create_task(self._tl._send_async(payload))
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._c, name)


class _AsyncWrappedChat:
    def __init__(self, chat: Any, tl: "TokenLens") -> None:
        self._chat = chat
        self.completions = _AsyncWrappedCompletions(chat.completions, tl)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class AsyncWrappedOpenAI:
    """Transparent proxy for openai.AsyncOpenAI."""

    def __init__(self, client: Any, tl: "TokenLens") -> None:
        self._client = client
        self._tl = tl
        self.chat = _AsyncWrappedChat(client.chat, tl)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


# ── Factory ────────────────────────────────────────────────────────────────────

def wrap_openai(client: Any, tl: "TokenLens") -> Any:
    """Return an AsyncWrappedOpenAI for async clients, WrappedOpenAI otherwise."""
    try:
        from openai import AsyncOpenAI
        if isinstance(client, AsyncOpenAI):
            return AsyncWrappedOpenAI(client, tl)
    except ImportError:
        pass
    return WrappedOpenAI(client, tl)
