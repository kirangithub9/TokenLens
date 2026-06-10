"""
tokenlens — Python SDK for TokenLens AI token and cost tracking.

Quick start
-----------
    from tokenlens import TokenLens

    tl = TokenLens(api_key="tl-...", base_url="http://localhost:8000")

    # OpenAI — one line, no separate import needed:
    client = tl.openai()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What is 2 + 2?"}],
    )
    # Token counts and cost are logged to TokenLens automatically.

    # Anthropic — same pattern:
    claude = tl.anthropic()
    msg = claude.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=256,
        messages=[{"role": "user", "content": "What is 2 + 2?"}],
    )

Bring-your-own client (custom settings, Azure, proxy, etc.)
------------------------------------------------------------
    from openai import OpenAI
    client = tl.wrap(OpenAI(base_url="https://...", api_key="..."))

Manual logging
--------------
    tl.log(
        model="gpt-4o-mini",
        tokens_in=150,
        tokens_out=42,
        latency_ms=830.5,
        query_text="What is 2 + 2?",
    )

Cost utilities
--------------
    from tokenlens.pricing import compute_cost, list_models
    cost = compute_cost("gpt-4o-mini", tokens_in=150, tokens_out=42)
    # {"usd": 0.00002745, "inr": 0.00233325}
"""

from .client import TokenLens
from .exceptions import AuthError, LoggingError, TokenLensError

__version__ = "0.1.0"
__all__ = ["TokenLens", "TokenLensError", "AuthError", "LoggingError"]
