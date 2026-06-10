"""
agent_proxy.py — TokenLens Agent Proxy
---------------------------------------
Authenticate with your tl- API key.  Every LLM call is logged: model,
tokens, cost, tools invoked, and the full conversation trace.

Endpoints
---------
POST /v1/agent/run                 — Start a run (returns tool_calls or final response)
POST /v1/agent/run/{run_id}/continue  — Supply tool results and continue
GET  /v1/agent/runs                — List your runs (Firebase auth, for the dashboard)
"""

import json
import logging
import os
import time
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database import (
    SessionLocal,
    create_agent_run,
    set_agent_run_progress,
    get_agent_run,
    get_agent_runs_for_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/agent", tags=["Agent Proxy"])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
USD_TO_INR     = float(os.getenv("USD_TO_INR", "85.0"))

# (input_per_token_usd, output_per_token_usd)
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":   (0.150  / 1_000_000, 0.600  / 1_000_000),
    "gpt-4o":        (5.00   / 1_000_000, 15.00  / 1_000_000),
    "gpt-4":         (30.00  / 1_000_000, 60.00  / 1_000_000),
    "gpt-4-turbo":   (10.00  / 1_000_000, 30.00  / 1_000_000),
    "gpt-3.5-turbo": (0.50   / 1_000_000, 1.50   / 1_000_000),
    "gemma":         (0.10   / 1_000_000, 0.40   / 1_000_000),
}


def _cost(tokens_in: int, tokens_out: int, model: str) -> tuple[float, float]:
    in_r, out_r = _PRICING.get(model.lower(), _PRICING["gpt-4o-mini"])
    usd = tokens_in * in_r + tokens_out * out_r
    return round(usd, 8), round(usd * USD_TO_INR, 6)


async def _call_openai(
    messages: list[dict],
    model: str,
    tools: list[dict] | None,
) -> tuple[dict, int, int, float]:
    """
    Call OpenAI Chat Completions.
    Returns (assistant_message_dict, tokens_in, tokens_out, latency_ms).
    """
    if not OPENAI_API_KEY:
        raise HTTPException(503, "OPENAI_API_KEY is not configured on this server.")

    payload: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type":  "application/json",
            },
        )
    latency_ms = (time.perf_counter() - t0) * 1000

    if r.status_code != 200:
        raise HTTPException(r.status_code, f"OpenAI error: {r.text}")

    data  = r.json()
    usage = data.get("usage", {})
    return (
        data["choices"][0]["message"],
        usage.get("prompt_tokens", 0),
        usage.get("completion_tokens", 0),
        latency_ms,
    )


# ── request / response models ─────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    agent_name: str
    model:      str = "gpt-4o-mini"
    messages:   list[dict]
    tools:      list[dict] | None = None


class ToolResult(BaseModel):
    tool_call_id: str
    name:         str
    content:      str


class AgentContinueRequest(BaseModel):
    tool_results: list[ToolResult]


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_user(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if not user or not user.get("uid"):
        raise HTTPException(401, "Authentication required.")
    return user["uid"]


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run")
async def start_run(body: AgentRunRequest, request: Request):
    """
    Start a new agent run.

    Auth: Authorization: Bearer tl-<your-key>

    Returns either:
      - {status: "completed", response, run_id, tokens_*, cost_*}
      - {status: "tool_pending", tool_calls, run_id, tokens_*, cost_*}
        → execute tool_calls locally, then POST to /run/{run_id}/continue
    """
    user_id = _require_user(request)
    run_id  = str(uuid.uuid4())

    query = next(
        (m["content"] for m in body.messages
         if isinstance(m.get("content"), str) and m.get("role") == "user"),
        None,
    )

    db = SessionLocal()
    try:
        create_agent_run(
            db,
            run_id        = run_id,
            user_id       = user_id,
            agent_name    = body.agent_name,
            model         = body.model,
            query         = query,
            tools_defined = json.dumps(body.tools) if body.tools else None,
            messages      = json.dumps(body.messages),
        )
    finally:
        db.close()

    try:
        message, tokens_in, tokens_out, latency_ms = await _call_openai(
            body.messages, body.model, body.tools
        )
    except HTTPException as exc:
        db = SessionLocal()
        try:
            set_agent_run_progress(
                db, run_id,
                status="error", tokens_in=0, tokens_out=0,
                cost_usd=0.0, cost_inr=0.0, latency_ms=0.0,
                error=str(exc.detail),
            )
        finally:
            db.close()
        raise

    cost_usd, cost_inr = _cost(tokens_in, tokens_out, body.model)
    updated_messages   = body.messages + [message]

    if message.get("tool_calls"):
        tools_called = [
            {
                "name":  tc["function"]["name"],
                "input": tc["function"].get("arguments", "{}"),
            }
            for tc in message["tool_calls"]
        ]
        db = SessionLocal()
        try:
            set_agent_run_progress(
                db, run_id,
                status       = "tool_pending",
                tokens_in    = tokens_in,
                tokens_out   = tokens_out,
                cost_usd     = cost_usd,
                cost_inr     = cost_inr,
                latency_ms   = latency_ms,
                tools_called = json.dumps(tools_called),
                messages     = json.dumps(updated_messages),
            )
        finally:
            db.close()

        return {
            "run_id":     run_id,
            "status":     "tool_pending",
            "tool_calls": message["tool_calls"],
            "tokens_in":  tokens_in,
            "tokens_out": tokens_out,
            "cost_usd":   cost_usd,
            "cost_inr":   cost_inr,
        }

    db = SessionLocal()
    try:
        set_agent_run_progress(
            db, run_id,
            status     = "completed",
            tokens_in  = tokens_in,
            tokens_out = tokens_out,
            cost_usd   = cost_usd,
            cost_inr   = cost_inr,
            latency_ms = latency_ms,
            response   = message.get("content", ""),
            messages   = json.dumps(updated_messages),
        )
    finally:
        db.close()

    return {
        "run_id":    run_id,
        "status":    "completed",
        "response":  message.get("content", ""),
        "tokens_in":  tokens_in,
        "tokens_out": tokens_out,
        "cost_usd":  cost_usd,
        "cost_inr":  cost_inr,
    }


@router.post("/run/{run_id}/continue")
async def continue_run(run_id: str, body: AgentContinueRequest, request: Request):
    """
    Resume a tool_pending run by supplying the tool results.
    May return another tool_pending if the LLM calls more tools.
    """
    user_id = _require_user(request)

    db = SessionLocal()
    try:
        run = get_agent_run(db, run_id)
        if not run or run.user_id != user_id:
            raise HTTPException(404, "Run not found.")
        if run.status != "tool_pending":
            raise HTTPException(400, f"Run is '{run.status}', expected 'tool_pending'.")

        messages      = json.loads(run.messages      or "[]")
        model         = run.model
        tools_defined = json.loads(run.tools_defined or "null")
        prev_called   = json.loads(run.tools_called  or "[]")
        acc_in        = run.tokens_in
        acc_out       = run.tokens_out
        acc_usd       = run.cost_usd
        acc_inr       = run.cost_inr
        acc_lat       = run.latency_ms
    finally:
        db.close()

    for tr in body.tool_results:
        messages.append({
            "role":         "tool",
            "tool_call_id": tr.tool_call_id,
            "name":         tr.name,
            "content":      tr.content,
        })

    message, tokens_in, tokens_out, latency_ms = await _call_openai(
        messages, model, tools_defined
    )

    cost_usd, cost_inr = _cost(tokens_in, tokens_out, model)
    total_in   = acc_in  + tokens_in
    total_out  = acc_out + tokens_out
    total_usd  = round(acc_usd + cost_usd, 8)
    total_inr  = round(acc_inr + cost_inr, 6)
    total_lat  = round(acc_lat + latency_ms, 2)
    updated_messages = messages + [message]

    if message.get("tool_calls"):
        new_called = prev_called + [
            {"name": tc["function"]["name"], "input": tc["function"].get("arguments", "{}")}
            for tc in message["tool_calls"]
        ]
        db = SessionLocal()
        try:
            set_agent_run_progress(
                db, run_id,
                status       = "tool_pending",
                tokens_in    = total_in,
                tokens_out   = total_out,
                cost_usd     = total_usd,
                cost_inr     = total_inr,
                latency_ms   = total_lat,
                tools_called = json.dumps(new_called),
                messages     = json.dumps(updated_messages),
            )
        finally:
            db.close()

        return {
            "run_id":     run_id,
            "status":     "tool_pending",
            "tool_calls": message["tool_calls"],
        }

    db = SessionLocal()
    try:
        set_agent_run_progress(
            db, run_id,
            status       = "completed",
            tokens_in    = total_in,
            tokens_out   = total_out,
            cost_usd     = total_usd,
            cost_inr     = total_inr,
            latency_ms   = total_lat,
            tools_called = json.dumps(prev_called),
            response     = message.get("content", ""),
            messages     = json.dumps(updated_messages),
        )
    finally:
        db.close()

    return {
        "run_id":     run_id,
        "status":     "completed",
        "response":   message.get("content", ""),
        "tokens_in":  total_in,
        "tokens_out": total_out,
        "cost_usd":   total_usd,
        "cost_inr":   total_inr,
    }


@router.get("/runs")
def list_runs(request: Request, limit: int = 100):
    """Return all agent runs for the authenticated user (Firebase or tl- key)."""
    user_id = _require_user(request)
    db = SessionLocal()
    try:
        runs = get_agent_runs_for_user(db, user_id, limit=limit)
        return [
            {
                "run_id":        r.run_id,
                "agent_name":    r.agent_name,
                "model":         r.model,
                "query":         r.query,
                "response":      r.response,
                "status":        r.status,
                "tokens_in":     r.tokens_in,
                "tokens_out":    r.tokens_out,
                "cost_usd":      r.cost_usd,
                "cost_inr":      r.cost_inr,
                "latency_ms":    r.latency_ms,
                "tools_defined": json.loads(r.tools_defined) if r.tools_defined else [],
                "tools_called":  json.loads(r.tools_called)  if r.tools_called  else [],
                "messages":      json.loads(r.messages)       if r.messages       else [],
                "started_at":    r.started_at.isoformat()    if r.started_at    else None,
                "finished_at":   r.finished_at.isoformat()   if r.finished_at   else None,
                "error":         r.error,
            }
            for r in runs
        ]
    finally:
        db.close()
