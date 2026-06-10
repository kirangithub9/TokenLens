"""
chat.py — TokenLens-hosted chat client.

Routes LLM calls through the TokenLens backend instead of directly to OpenAI/Anthropic.
Only the tl- API key is required — no provider key needed in your app.

    client = tl.chat()
    response = client.completions.create(
        model="gpt4o-mini",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print(response.choices[0].message.content)
"""
from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Optional

import httpx

from .exceptions import LoggingError

if TYPE_CHECKING:
    from .client import TokenLens


# ── Lightweight response objects that mirror the OpenAI shape ─────────────────

class _Message:
    def __init__(self, content: str, role: str = "assistant"):
        self.content = content
        self.role = role


class _Choice:
    def __init__(self, message: _Message, index: int = 0):
        self.message = message
        self.index = index
        self.finish_reason = "stop"


class _Usage:
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class _Cost:
    def __init__(self, usd: float, inr: float):
        self.usd = usd
        self.inr = inr


class ChatCompletion:
    """
    Response object from tl.chat().completions.create().
    Mirrors openai.types.chat.ChatCompletion so callers can use the same
    attribute access pattern regardless of whether they go direct or via TokenLens.
    """

    def __init__(self, data: dict):
        content = data.get("response", "")
        self.choices = [_Choice(_Message(content))]
        u = data.get("usage", {})
        self.usage = _Usage(
            prompt_tokens=u.get("prompt_tokens", 0),
            completion_tokens=u.get("completion_tokens", 0),
        )
        cost = data.get("cost", {})
        self.cost = _Cost(usd=cost.get("usd", 0.0), inr=cost.get("inr", 0.0))
        self.latency_ms = data.get("latency_ms", 0.0)
        self.model = data.get("model", "")
        self._raw = data

    def __repr__(self) -> str:
        return (
            f"ChatCompletion(content={self.choices[0].message.content[:60]!r}, "
            f"tokens={self.usage.total_tokens}, cost_usd={self.cost.usd:.8f})"
        )


# ── Async response ─────────────────────────────────────────────────────────────

class AsyncChatCompletion(ChatCompletion):
    pass


# ── Completions resource ───────────────────────────────────────────────────────

class _Completions:
    def __init__(self, session_id: str, tl: "TokenLens") -> None:
        self._session_id = session_id
        self._tl = tl

    def create(
        self,
        *,
        messages: list[dict],
        model: str = "gemma",
        **_,
    ) -> ChatCompletion:
        """
        Send a chat request through the TokenLens backend.

        Args:
            messages: List of {"role": "user"/"assistant"/"system", "content": "..."}.
                      The last user message is sent to the backend.
            model:    Model to use — must match one configured in your backend
                      ("gemma", "gpt4", "gpt4o-mini", etc.).

        Returns:
            ChatCompletion with .choices[0].message.content, .usage, .cost, .latency_ms
        """
        payload = self._build_payload(messages, model)
        with httpx.Client(timeout=self._tl._timeout) as http:
            try:
                r = http.post(
                    f"{self._tl._base_url}/chat",
                    json=payload,
                    headers=self._tl._headers,
                )
            except httpx.RequestError as exc:
                raise LoggingError(f"Could not reach TokenLens backend: {exc}") from exc

        if r.status_code != 200:
            raise LoggingError(
                f"TokenLens backend returned {r.status_code}: {r.text[:300]}"
            )
        result = ChatCompletion(r.json())
        # Also log to /v1/log so the call appears in api_usage (SDK usage view).
        self._tl._log_background(
            model=model,
            tokens_in=result.usage.prompt_tokens,
            tokens_out=result.usage.completion_tokens,
            latency_ms=result.latency_ms,
            query_text=_extract_last_user(messages),
        )
        return result

    def _build_payload(self, messages: list[dict], model: str) -> dict:
        last_user = _extract_last_user(messages)
        return {
            "session_id": self._session_id,
            "user_id":    "sdk",
            "message":    last_user,
            "model":      model,
        }


class _AsyncCompletions:
    def __init__(self, session_id: str, tl: "TokenLens") -> None:
        self._session_id = session_id
        self._tl = tl

    async def create(
        self,
        *,
        messages: list[dict],
        model: str = "gemma",
        **_,
    ) -> ChatCompletion:
        payload = {
            "session_id": self._session_id,
            "user_id":    "sdk",
            "message":    _extract_last_user(messages),
            "model":      model,
        }
        async with httpx.AsyncClient(timeout=self._tl._timeout) as http:
            try:
                r = await http.post(
                    f"{self._tl._base_url}/chat",
                    json=payload,
                    headers=self._tl._headers,
                )
            except httpx.RequestError as exc:
                raise LoggingError(f"Could not reach TokenLens backend: {exc}") from exc

        if r.status_code != 200:
            raise LoggingError(
                f"TokenLens backend returned {r.status_code}: {r.text[:300]}"
            )
        result = ChatCompletion(r.json())
        # Also log to /v1/log so the call appears in api_usage (SDK usage view).
        log_payload = self._tl._build_payload(
            model,
            result.usage.prompt_tokens,
            result.usage.completion_tokens,
            result.latency_ms,
            _extract_last_user(messages),
            None,
        )
        asyncio.get_event_loop().create_task(self._tl._send_async(log_payload))
        return result


# ── Chat resource (holds completions) ─────────────────────────────────────────

class _Chat:
    def __init__(self, session_id: str, tl: "TokenLens") -> None:
        self.completions = _Completions(session_id, tl)


class _AsyncChat:
    def __init__(self, session_id: str, tl: "TokenLens") -> None:
        self.completions = _AsyncCompletions(session_id, tl)


# ── Public client classes ──────────────────────────────────────────────────────

class TokenLensChatClient:
    """
    Sync chat client that routes all LLM calls through the TokenLens backend.
    No provider API key needed — only your tl- key.

        client = tl.chat()
        response = client.chat.completions.create(
            model="gpt4o-mini",
            messages=[{"role": "user", "content": "Hello!"}],
        )
    """

    def __init__(self, tl: "TokenLens", session_id: Optional[str] = None) -> None:
        self._tl = tl
        self._session_id = session_id or str(uuid.uuid4())
        self.chat = _Chat(self._session_id, tl)


class AsyncTokenLensChatClient:
    """
    Async chat client that routes all LLM calls through the TokenLens backend.

        client = tl.async_chat()
        response = await client.chat.completions.create(...)
    """

    def __init__(self, tl: "TokenLens", session_id: Optional[str] = None) -> None:
        self._tl = tl
        self._session_id = session_id or str(uuid.uuid4())
        self.chat = _AsyncChat(self._session_id, tl)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_last_user(messages: list[dict]) -> str:
    """Return the content of the last user message, or empty string."""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
    return ""
