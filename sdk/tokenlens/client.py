"""
client.py — TokenLens main client.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import httpx

from .exceptions import AuthError, LoggingError

logger = logging.getLogger("tokenlens")


class TokenLens:
    """
    TokenLens SDK client — tracks tokens, latency, and cost for every AI call.

    Quick start:
        from tokenlens import TokenLens
        from openai import OpenAI

        tl = TokenLens(api_key="tl-...", base_url="http://localhost:8000")
        client = tl.wrap(OpenAI())

        # Identical to the normal OpenAI API — logging is transparent.
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello!"}],
        )

    Manual logging:
        tl.log(model="gpt-4o-mini", tokens_in=150, tokens_out=42, latency_ms=830)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        application: str = "tokenlens-sdk",
        background: bool = True,
        timeout: float = 10.0,
        raise_on_error: bool = False,
    ):
        """
        Args:
            api_key:        Your TokenLens API key (starts with "tl-").
                            Generate one from the TokenLens dashboard under API Keys.
            base_url:       Base URL of your TokenLens backend (default: localhost).
            application:    Label shown in the dashboard for these log entries.
            background:     When True (default), log() sends the request in a background
                            thread and returns None immediately. Set False to block and
                            get the response dict back.
            timeout:        HTTP timeout in seconds for log requests (default 10).
            raise_on_error: Raise LoggingError on failed log requests instead of
                            silently warning (default False — never interrupt user code).
        """
        if not api_key:
            raise AuthError("api_key is required. Generate one from the TokenLens dashboard.")
        if not api_key.startswith("tl-"):
            raise AuthError("api_key must start with 'tl-'. Check the TokenLens dashboard.")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._application = application
        self._background = background
        self._timeout = timeout
        self._raise_on_error = raise_on_error
        self._log_url = f"{self._base_url}/v1/log"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ── Public API ─────────────────────────────────────────────────────────────

    def log(
        self,
        *,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        query_text: Optional[str] = None,
        application: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Log a single AI request.

        Args:
            model:       Model identifier (e.g. "gpt-4o-mini", "claude-3-5-sonnet-20241022").
            tokens_in:   Prompt / input token count.
            tokens_out:  Completion / output token count.
            latency_ms:  End-to-end request latency in milliseconds.
            query_text:  Optional: first 500 chars of the user's message (for dashboard preview).
            application: Override the default application label for this entry.

        Returns:
            {"usage_id": str, "cost_usd": float, "cost_inr": float} when background=False.
            None when background=True (fire-and-forget, default).
        """
        payload = self._build_payload(model, tokens_in, tokens_out, latency_ms, query_text, application)
        if self._background:
            threading.Thread(target=self._send_sync, args=(payload,), daemon=True).start()
            return None
        return self._send_sync(payload)

    async def alog(
        self,
        *,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        query_text: Optional[str] = None,
        application: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Async version of log(). Awaits the HTTP request and returns the response dict.

        Use inside async application code or async tests.
        """
        payload = self._build_payload(model, tokens_in, tokens_out, latency_ms, query_text, application)
        return await self._send_async(payload)

    def wrap(self, client: Any) -> Any:
        """
        Wrap an existing AI provider client to log every request automatically.

        Supported client types:
            openai.OpenAI            — sync OpenAI client
            openai.AsyncOpenAI       — async OpenAI client
            anthropic.Anthropic      — sync Anthropic client
            anthropic.AsyncAnthropic — async Anthropic client

        Returns a transparent proxy: all methods other than the tracked ones pass
        through unchanged, so existing code works without any other modifications.

        Use wrap() when you need custom client settings (Azure base_url, org ID,
        proxy, timeout, etc.). For the default case, prefer tl.openai() or
        tl.anthropic() which create and wrap the client in one call.
        """
        module = type(client).__module__

        if "openai" in module:
            from .wrappers.openai import wrap_openai
            return wrap_openai(client, self)

        if "anthropic" in module:
            from .wrappers.anthropic import wrap_anthropic
            return wrap_anthropic(client, self)

        raise TypeError(
            f"Unsupported client type: {type(client).__qualname__!r}. "
            "Supported: openai.OpenAI, openai.AsyncOpenAI, "
            "anthropic.Anthropic, anthropic.AsyncAnthropic."
        )

    def chat(self, session_id: Optional[str] = None) -> Any:
        """
        Create a sync chat client that routes LLM calls through the TokenLens backend.

        No provider API key needed — the backend uses its own configured LLM keys.
        Only your tl- API key is required.

        Args:
            session_id: Reuse an existing session to maintain conversation memory.
                        Omit to start a fresh session (a UUID is generated automatically).

        Example:
            client = tl.chat()
            response = client.chat.completions.create(
                model="gpt4o-mini",
                messages=[{"role": "user", "content": "Hello!"}],
            )
            print(response.choices[0].message.content)
            print(response.cost.usd)
        """
        from .chat import TokenLensChatClient
        return TokenLensChatClient(self, session_id=session_id)

    def async_chat(self, session_id: Optional[str] = None) -> Any:
        """
        Create an async chat client that routes LLM calls through the TokenLens backend.

        Example:
            client = tl.async_chat()
            response = await client.chat.completions.create(
                model="gpt4o-mini",
                messages=[{"role": "user", "content": "Hello!"}],
            )
        """
        from .chat import AsyncTokenLensChatClient
        return AsyncTokenLensChatClient(self, session_id=session_id)

    def openai(self, **kwargs) -> Any:
        """
        Create a tracked OpenAI client in one call — no separate import needed.

        Equivalent to: tl.wrap(OpenAI(**kwargs))

        Any keyword arguments are forwarded directly to openai.OpenAI(), so you
        can still pass api_key, base_url (Azure), organization, timeout, etc.

        Example:
            client = tl.openai()
            response = client.chat.completions.create(model="gpt-4o-mini", ...)
        """
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package is not installed. Run: pip install tokenlens-sdk[openai]"
            ) from exc
        from .wrappers.openai import wrap_openai
        return wrap_openai(OpenAI(**kwargs), self)

    def async_openai(self, **kwargs) -> Any:
        """
        Create a tracked AsyncOpenAI client in one call.

        Equivalent to: tl.wrap(AsyncOpenAI(**kwargs))
        """
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package is not installed. Run: pip install tokenlens-sdk[openai]"
            ) from exc
        from .wrappers.openai import wrap_openai
        return wrap_openai(AsyncOpenAI(**kwargs), self)

    def anthropic(self, **kwargs) -> Any:
        """
        Create a tracked Anthropic client in one call — no separate import needed.

        Equivalent to: tl.wrap(Anthropic(**kwargs))

        Example:
            client = tl.anthropic()
            response = client.messages.create(model="claude-3-5-haiku-20241022", ...)
        """
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is not installed. Run: pip install tokenlens-sdk[anthropic]"
            ) from exc
        from .wrappers.anthropic import wrap_anthropic
        return wrap_anthropic(Anthropic(**kwargs), self)

    def async_anthropic(self, **kwargs) -> Any:
        """
        Create a tracked AsyncAnthropic client in one call.

        Equivalent to: tl.wrap(AsyncAnthropic(**kwargs))
        """
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is not installed. Run: pip install tokenlens-sdk[anthropic]"
            ) from exc
        from .wrappers.anthropic import wrap_anthropic
        return wrap_anthropic(AsyncAnthropic(**kwargs), self)

    # ── Internal helpers (used by wrappers) ────────────────────────────────────

    def _build_payload(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        query_text: Optional[str],
        application: Optional[str],
    ) -> dict:
        return {
            "application": application or self._application,
            "model_used":  model,
            "tokens_in":   tokens_in,
            "tokens_out":  tokens_out,
            "latency_ms":  round(latency_ms, 2),
            "query_text":  (query_text or "")[:500] or None,
        }

    def _log_background(
        self,
        *,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        query_text: Optional[str] = None,
        application: Optional[str] = None,
    ) -> None:
        """Fire-and-forget sync log — called by sync wrappers after each LLM response."""
        payload = self._build_payload(model, tokens_in, tokens_out, latency_ms, query_text, application)
        threading.Thread(target=self._send_sync, args=(payload,), daemon=True).start()

    def _send_sync(self, payload: dict) -> Optional[dict]:
        try:
            with httpx.Client(timeout=self._timeout) as http:
                r = http.post(self._log_url, json=payload, headers=self._headers)
            return self._handle_response(r)
        except httpx.RequestError as exc:
            return self._handle_request_error(exc)

    async def _send_async(self, payload: dict) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                r = await http.post(self._log_url, json=payload, headers=self._headers)
            return self._handle_response(r)
        except httpx.RequestError as exc:
            return self._handle_request_error(exc)

    def _handle_response(self, r: httpx.Response) -> Optional[dict]:
        if r.status_code == 200:
            return r.json()
        err = LoggingError(f"TokenLens backend returned {r.status_code}: {r.text[:200]}")
        if self._raise_on_error:
            raise err
        logger.warning("%s", err)
        return None

    def _handle_request_error(self, exc: httpx.RequestError) -> Optional[dict]:
        err = LoggingError(f"Could not reach TokenLens backend at {self._base_url}: {exc}")
        if self._raise_on_error:
            raise err
        logger.warning("%s", err)
        return None
