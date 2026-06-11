"""
sdk_log.py — TokenLens SDK Logging Endpoint
POST /v1/log  — Accept token/latency data from the SDK, persist to:
  • api_usage   (always)
  • agent_runs  (when agent_name is provided — shows up in Agent Runs page)
Auth: Authorization: Bearer tl-<api_key>
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database import SessionLocal
from database.db import log_api_usage, log_sdk_agent_run

router = APIRouter(prefix="/v1", tags=["SDK"])

USD_TO_INR = float(os.getenv("USD_TO_INR", "85.0"))

_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o":                     {"input": 5.00  / 1_000_000, "output": 20.00 / 1_000_000},
    "gpt-4o-mini":                {"input": 0.15  / 1_000_000, "output": 0.60  / 1_000_000},
    "gpt-4-turbo":                {"input": 10.00 / 1_000_000, "output": 30.00 / 1_000_000},
    "gpt-4":                      {"input": 30.00 / 1_000_000, "output": 60.00 / 1_000_000},
    "gpt-3.5-turbo":              {"input": 0.50  / 1_000_000, "output": 1.50  / 1_000_000},
    "o1":                         {"input": 15.00 / 1_000_000, "output": 60.00 / 1_000_000},
    "o1-mini":                    {"input": 3.00  / 1_000_000, "output": 12.00 / 1_000_000},
    "o3":                         {"input": 10.00 / 1_000_000, "output": 40.00 / 1_000_000},
    "o3-mini":                    {"input": 1.10  / 1_000_000, "output": 4.40  / 1_000_000},
    # Anthropic
    "claude-opus-4-8":            {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
    "claude-sonnet-4-6":          {"input": 3.00  / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-haiku-4-5-20251001":  {"input": 0.80  / 1_000_000, "output": 4.00  / 1_000_000},
    "claude-3-5-sonnet-20241022": {"input": 3.00  / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-3-5-haiku-20241022":  {"input": 0.80  / 1_000_000, "output": 4.00  / 1_000_000},
    "claude-3-opus-20240229":     {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
    "claude-3-haiku-20240307":    {"input": 0.25  / 1_000_000, "output": 1.25  / 1_000_000},
    # Google Gemini
    "gemini-1.5-pro":             {"input": 1.25  / 1_000_000, "output": 5.00  / 1_000_000},
    "gemini-1.5-flash":           {"input": 0.075 / 1_000_000, "output": 0.30  / 1_000_000},
    "gemini-2.0-flash":           {"input": 0.10  / 1_000_000, "output": 0.40  / 1_000_000},
    "gemini-2.0-flash-lite":      {"input": 0.075 / 1_000_000, "output": 0.30  / 1_000_000},
    # TokenLens backend aliases
    "gemma":                      {"input": 0.10  / 1_000_000, "output": 0.40  / 1_000_000},
    "gpt4":                       {"input": 0.15  / 1_000_000, "output": 0.60  / 1_000_000},
    "gpt4o-mini":                 {"input": 0.15  / 1_000_000, "output": 0.60  / 1_000_000},
}

_DEFAULT_PRICING = {"input": 0.001 / 1_000_000, "output": 0.002 / 1_000_000}

_SUPPORTED_MODELS = set(_PRICING.keys())


def _compute_cost(model: str, tokens_in: int, tokens_out: int) -> tuple[float, float]:
    p = _PRICING.get(model.lower(), _DEFAULT_PRICING)
    usd = tokens_in * p["input"] + tokens_out * p["output"]
    return round(usd, 8), round(usd * USD_TO_INR, 6)


class LogRequest(BaseModel):
    application:   str
    agent_name:    Optional[str] = None        # if set → also written to agent_runs
    model_used:    str
    tokens_in:     int
    tokens_out:    int
    latency_ms:    float
    query_text:    Optional[str] = None
    response_text: Optional[str] = None        # assistant reply captured by wrappers


class LogResponse(BaseModel):
    usage_id:     str
    cost_usd:     float
    cost_inr:     float
    total_tokens: int
    model_found:  bool                         # False when model fell back to default pricing


@router.post("/log", response_model=LogResponse, summary="Log an AI request from the SDK")
def sdk_log(body: LogRequest, request: Request):
    """
    Accept token/latency data from the TokenLens SDK and persist it.

    • Always writes to api_usage table (existing metrics dashboard).
    • When agent_name is provided, also writes a completed run to agent_runs
      so it appears in the Agent Runs page with full token/cost detail.

    Returns model_found=False when the model is unknown (cost is estimated).
    """
    # ── model validation ───────────────────────────────────────────────────────
    model_key = body.model_used.lower()
    model_found = model_key in _SUPPORTED_MODELS

    cost_usd, cost_inr = _compute_cost(model_key, body.tokens_in, body.tokens_out)
    total_tokens = body.tokens_in + body.tokens_out

    # ── get user_id from auth middleware ───────────────────────────────────────
    user = getattr(request.state, "user", None)
    user_id: Optional[str] = user.get("uid") if user else None

    db = SessionLocal()
    try:
        # Always write to api_usage
        record = log_api_usage(
            db,
            application = body.application,
            query_text  = body.query_text,
            model_used  = body.model_used,
            tokens_in   = body.tokens_in,
            tokens_out  = body.tokens_out,
            cost_usd    = cost_usd,
            cost_inr    = cost_inr,
            latency_ms  = body.latency_ms,
        )

        # Write to agent_runs when agent_name is provided and user is authenticated
        if body.agent_name and user_id:
            log_sdk_agent_run(
                db,
                user_id       = user_id,
                agent_name    = body.agent_name,
                model         = body.model_used,
                query_text    = body.query_text,
                response_text = body.response_text,
                tokens_in     = body.tokens_in,
                tokens_out    = body.tokens_out,
                cost_usd      = cost_usd,
                cost_inr      = cost_inr,
                latency_ms    = body.latency_ms,
            )
    finally:
        db.close()

    return LogResponse(
        usage_id     = record.usage_id,
        cost_usd     = cost_usd,
        cost_inr     = cost_inr,
        total_tokens = total_tokens,
        model_found  = model_found,
    )


@router.get("/models", summary="List all supported models and their pricing")
def list_models():
    """Return every model the SDK recognises with its USD pricing per token."""
    return {
        model: {
            "input_per_token_usd":  pricing["input"],
            "output_per_token_usd": pricing["output"],
        }
        for model, pricing in _PRICING.items()
    }
