"""
client.py — TokenLens main client.
"""
from __future__ import annotations

import logging
import os
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

        tl = TokenLens(api_key="tl-...", base_url="http://localhost:8000",
                       agent_name="my-agent")

        # OpenAI — wrap and go:
        client = tl.openai()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello!"}],
        )

        # Anthropic:
        claude = tl.anthropic()
        msg = claude.messages.create(model="claude-3-5-haiku-20241022", ...)

        # Google Gemini:
        gemini = tl.gemini("gemini-1.5-flash")
        response = gemini.generate_content("What is 2 + 2?")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = os.getenv("TOKENLENS_URL", "http://localhost:8000"),
        application: str = "tokenlens-sdk",
        agent_name: str = "tokenlens-agent",
        background: bool = True,
        timeout: float = 10.0,
        raise_on_error: bool = False,
    ):
        """
        Args:
            api_key:        Your TokenLens API key (starts with "tl-").
            base_url:       Base URL of your TokenLens backend. Defaults to the
                            TOKENLENS_URL environment variable, falling back to
                            "http://localhost:8000".
            application:    App/service label shown in the dashboard.
            agent_name:     Name of this agent — shown in Agent Runs page.
            background:     When True (default), log() fires in a background thread.
            timeout:        HTTP timeout in seconds for log requests (default 10).
            raise_on_error: Raise LoggingError on failed requests (default False).
        """
        if not api_key:
            raise AuthError("api_key is required. Generate one from the TokenLens dashboard.")
        if not api_key.startswith("tl-"):
            raise AuthError("api_key must start with 'tl-'. Check the TokenLens dashboard.")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._application = application
        self._agent_name = agent_name
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
        response_text: Optional[str] = None,
        application: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Log a single AI request manually.

        Args:
            model:         Model identifier (e.g. "gpt-4o-mini").
            tokens_in:     Prompt / input token count.
            tokens_out:    Completion / output token count.
            latency_ms:    End-to-end latency in milliseconds.
            query_text:    First 500 chars of the user's message (optional).
            response_text: First 1000 chars of the assistant's reply (optional).
            application:   Override the default application label.

        Returns:
            {"usage_id": str, "cost_usd": float, "cost_inr": float} if background=False.
            None if background=True (fire-and-forget, default).
        """
        payload = self._build_payload(
            model, tokens_in, tokens_out, latency_ms, query_text, application, response_text
        )
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
        response_text: Optional[str] = None,
        application: Optional[str] = None,
    ) -> Optional[dict]:
        """Async version of log(). Awaits the HTTP request and returns the response dict."""
        payload = self._build_payload(
            model, tokens_in, tokens_out, latency_ms, query_text, application, response_text
        )
        return await self._send_async(payload)

    def wrap(self, client: Any) -> Any:
        """
        Wrap an existing AI provider client to log every request automatically.

        Supported providers (auto-detected from installed wrappers):
            openai.OpenAI / openai.AsyncOpenAI
            anthropic.Anthropic / anthropic.AsyncAnthropic
            google.generativeai.GenerativeModel

        Adding a new provider: create wrappers/<provider>.py — it is picked up
        automatically on next import without any changes to this file.

        Raises TypeError if no wrapper matches the client's module.
        """
        from .wrappers import REGISTRY
        module = type(client).__module__

        for provider_key, wrap_fn in REGISTRY.items():
            if provider_key in module:
                return wrap_fn(client, self)

        supported = ", ".join(sorted(REGISTRY.keys())) or "none installed"
        raise TypeError(
            f"Provider '{type(client).__qualname__}' (module: '{module}') is not supported. "
            f"Supported providers: {supported}. "
            f"To add support, create sdk/tokenlens/wrappers/<provider>.py and add the "
            f"package to pyproject.toml dependencies."
        )

    def chat(self, session_id: Optional[str] = None) -> Any:
        """Create a sync chat client that routes LLM calls through the TokenLens backend."""
        from .chat import TokenLensChatClient
        return TokenLensChatClient(self, session_id=session_id)

    def async_chat(self, session_id: Optional[str] = None) -> Any:
        """Create an async chat client that routes LLM calls through the TokenLens backend."""
        from .chat import AsyncTokenLensChatClient
        return AsyncTokenLensChatClient(self, session_id=session_id)

    def openai(self, **kwargs) -> Any:
        """
        Create a tracked OpenAI client in one call.

        Equivalent to: tl.wrap(OpenAI(**kwargs))

        Example:
            client = tl.openai()
            response = client.chat.completions.create(model="gpt-4o-mini", ...)
        """
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package is not installed. Run: pip install tokenlens"
            ) from exc
        from .wrappers.openai import wrap_openai
        return wrap_openai(OpenAI(**kwargs), self)

    def async_openai(self, **kwargs) -> Any:
        """Create a tracked AsyncOpenAI client in one call."""
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package is not installed. Run: pip install tokenlens"
            ) from exc
        from .wrappers.openai import wrap_openai
        return wrap_openai(AsyncOpenAI(**kwargs), self)

    def anthropic(self, **kwargs) -> Any:
        """
        Create a tracked Anthropic client in one call.

        Example:
            client = tl.anthropic()
            response = client.messages.create(model="claude-3-5-haiku-20241022", ...)
        """
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is not installed. Run: pip install tokenlens"
            ) from exc
        from .wrappers.anthropic import wrap_anthropic
        return wrap_anthropic(Anthropic(**kwargs), self)

    def async_anthropic(self, **kwargs) -> Any:
        """Create a tracked AsyncAnthropic client in one call."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is not installed. Run: pip install tokenlens"
            ) from exc
        from .wrappers.anthropic import wrap_anthropic
        return wrap_anthropic(AsyncAnthropic(**kwargs), self)

    def ollama(self, base_url: str | None = None, **kwargs) -> Any:
        """
        Create a tracked Ollama client. Uses the OpenAI-compatible API that
        Ollama exposes — no extra package needed beyond openai.

        base_url defaults to OLLAMA_HOST env var + /v1, falling back to
        http://localhost:11434/v1.

        Example:
            client = tl.ollama()
            response = client.chat.completions.create(
                model="gemma",
                messages=[{"role": "user", "content": "Hello!"}]
            )
        """
        import os
        if base_url is None:
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            base_url = f"{host.rstrip('/')}/v1"
        from .wrappers.ollama import wrap_ollama
        return wrap_ollama(base_url, self, **kwargs)

    # ── Internal helpers (used by wrappers) ────────────────────────────────────

    def _build_payload(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        query_text: Optional[str],
        application: Optional[str],
        response_text: Optional[str] = None,
    ) -> dict:
        return {
            "application":   application or self._application,
            "agent_name":    self._agent_name,
            "model_used":    model,
            "tokens_in":     tokens_in,
            "tokens_out":    tokens_out,
            "latency_ms":    round(latency_ms, 2),
            "query_text":    (query_text or "")[:500] or None,
            "response_text": (response_text or "")[:1000] or None,
        }

    def _log_background(
        self,
        *,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        query_text: Optional[str] = None,
        response_text: Optional[str] = None,
        application: Optional[str] = None,
    ) -> None:
        """Fire-and-forget sync log — called by sync wrappers after each LLM response."""
        payload = self._build_payload(
            model, tokens_in, tokens_out, latency_ms, query_text, application, response_text
        )
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
