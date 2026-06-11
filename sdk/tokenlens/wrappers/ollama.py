"""
wrappers/ollama.py — Tracked Ollama client (OpenAI-compatible API).

Ollama exposes an OpenAI-compatible endpoint, so this wrapper reuses the
OpenAI wrapper internally. No separate SDK needed — only openai is required.

Supports any model served by Ollama: gemma, llama3, mistral, etc.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import TokenLens

# No PROVIDER_MODULE — Ollama clients are openai.OpenAI instances at runtime.
# Use tl.ollama() instead of tl.wrap() for Ollama clients.


def wrap_ollama(base_url: str, tl: "TokenLens", **openai_kwargs: Any) -> Any:
    """Return a WrappedOpenAI proxy pointed at the given Ollama base URL."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "openai package is not installed. Run: pip install tokenlens"
        ) from exc
    from .openai import wrap_openai
    return wrap_openai(OpenAI(base_url=base_url, api_key="ollama", **openai_kwargs), tl)
