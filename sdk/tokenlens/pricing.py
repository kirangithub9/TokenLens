"""
pricing.py — Per-token USD pricing for popular LLM providers.

Used by TokenLens.log() callers who want a local cost estimate.
The backend also computes cost independently, so this is purely informational.
"""

from typing import Optional

# All prices are USD per token (not per 1 000 tokens).
_PRICING: dict[str, dict[str, float]] = {
    # ── OpenAI ──────────────────────────────────────────────────────────────────
    "gpt-4o":                     {"input": 5.00  / 1_000_000, "output": 20.00 / 1_000_000},
    "gpt-4o-mini":                {"input": 0.15  / 1_000_000, "output": 0.60  / 1_000_000},
    "gpt-4-turbo":                {"input": 10.00 / 1_000_000, "output": 30.00 / 1_000_000},
    "gpt-4":                      {"input": 30.00 / 1_000_000, "output": 60.00 / 1_000_000},
    "gpt-3.5-turbo":              {"input": 0.50  / 1_000_000, "output": 1.50  / 1_000_000},
    "o1":                         {"input": 15.00 / 1_000_000, "output": 60.00 / 1_000_000},
    "o1-mini":                    {"input": 3.00  / 1_000_000, "output": 12.00 / 1_000_000},
    "o1-preview":                 {"input": 15.00 / 1_000_000, "output": 60.00 / 1_000_000},
    "o3":                         {"input": 10.00 / 1_000_000, "output": 40.00 / 1_000_000},
    "o3-mini":                    {"input": 1.10  / 1_000_000, "output": 4.40  / 1_000_000},
    # ── Anthropic ────────────────────────────────────────────────────────────────
    "claude-opus-4-8":            {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
    "claude-sonnet-4-6":          {"input": 3.00  / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-haiku-4-5-20251001":  {"input": 0.80  / 1_000_000, "output": 4.00  / 1_000_000},
    "claude-3-5-sonnet-20241022": {"input": 3.00  / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-3-5-haiku-20241022":  {"input": 0.80  / 1_000_000, "output": 4.00  / 1_000_000},
    "claude-3-opus-20240229":     {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
    "claude-3-sonnet-20240229":   {"input": 3.00  / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-3-haiku-20240307":    {"input": 0.25  / 1_000_000, "output": 1.25  / 1_000_000},
    # ── Google ───────────────────────────────────────────────────────────────────
    "gemini-1.5-pro":             {"input": 1.25  / 1_000_000, "output": 5.00  / 1_000_000},
    "gemini-1.5-flash":           {"input": 0.075 / 1_000_000, "output": 0.30  / 1_000_000},
    "gemini-2.0-flash":           {"input": 0.10  / 1_000_000, "output": 0.40  / 1_000_000},
    "gemini-2.0-flash-lite":      {"input": 0.075 / 1_000_000, "output": 0.30  / 1_000_000},
    # ── TokenLens backend aliases ─────────────────────────────────────────────
    "gemma":                      {"input": 0.10  / 1_000_000, "output": 0.40  / 1_000_000},
    "gpt4":                       {"input": 0.15  / 1_000_000, "output": 0.60  / 1_000_000},
    "gpt4o-mini":                 {"input": 0.15  / 1_000_000, "output": 0.60  / 1_000_000},
}

_DEFAULT = {"input": 0.001 / 1_000_000, "output": 0.002 / 1_000_000}
_USD_TO_INR = 85.0


def compute_cost(
    model: str,
    tokens_in: int,
    tokens_out: int,
    usd_to_inr: float = _USD_TO_INR,
    custom_pricing: Optional[dict[str, float]] = None,
) -> dict[str, float]:
    """
    Compute the USD and INR cost for one LLM call.

    Args:
        model:          Model identifier (e.g. "gpt-4o-mini").
        tokens_in:      Input / prompt token count.
        tokens_out:     Output / completion token count.
        usd_to_inr:     Exchange rate override (default 85.0).
        custom_pricing: {"input": per_token_usd, "output": per_token_usd}
                        overrides the built-in table for the given call.

    Returns:
        {"usd": float, "inr": float}
    """
    p = custom_pricing or _PRICING.get(model.lower(), _DEFAULT)
    usd = tokens_in * p["input"] + tokens_out * p["output"]
    return {"usd": round(usd, 8), "inr": round(usd * usd_to_inr, 6)}


def list_models() -> list[str]:
    """Return all model names present in the built-in pricing table."""
    return sorted(_PRICING.keys())
