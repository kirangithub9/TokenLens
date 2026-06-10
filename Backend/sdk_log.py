"""
sdk_log.py — TokenLens SDK Logging Endpoint
POST /v1/log  — Accept token/latency data from the SDK, persist to ApiUsage table.
Auth: Authorization: Bearer tl-<api_key>
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database import SessionLocal
from database.db import log_api_usage

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
    # Google
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


def _compute_cost(model: str, tokens_in: int, tokens_out: int) -> tuple[float, float]:
    p = _PRICING.get(model.lower(), _DEFAULT_PRICING)
    usd = tokens_in * p["input"] + tokens_out * p["output"]
    return round(usd, 8), round(usd * USD_TO_INR, 6)


class LogRequest(BaseModel):
    application: str
    model_used:  str
    tokens_in:   int
    tokens_out:  int
    latency_ms:  float
    query_text:  Optional[str] = None


class LogResponse(BaseModel):
    usage_id: str
    cost_usd: float
    cost_inr: float


@router.post("/log", response_model=LogResponse, summary="Log an AI request from the SDK")
def sdk_log(body: LogRequest, request: Request):
    """
    Accept token/latency data from the TokenLens SDK and store it in the api_usage table.

    Requires:  Authorization: Bearer tl-<your-api-key>

    Cost is computed server-side from the built-in pricing table.
    Logged entries appear in the dashboard under SDK Usage.
    """
    user = getattr(request.state, "user", None)
    if not user or not user.get("uid"):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Use: Authorization: Bearer tl-<your-api-key>",
        )

    cost_usd, cost_inr = _compute_cost(body.model_used, body.tokens_in, body.tokens_out)

    db = SessionLocal()
    try:
        record = log_api_usage(
            db,
            application=body.application,
            query_text=body.query_text,
            model_used=body.model_used,
            tokens_in=body.tokens_in,
            tokens_out=body.tokens_out,
            cost_usd=cost_usd,
            cost_inr=cost_inr,
            latency_ms=body.latency_ms,
        )
    finally:
        db.close()

    return LogResponse(usage_id=record.usage_id, cost_usd=cost_usd, cost_inr=cost_inr)
