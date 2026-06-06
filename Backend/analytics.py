"""
analytics.py  —  TokenLens User Analytics Router
─────────────────────────────────────────────────
Drop this file into your Backend/ folder and register it in main.py:

    from analytics import router as analytics_router
    app.include_router(analytics_router)

Endpoints:
    GET  /analytics/user/{user_id}          — full profile: tokens, cost, models
    GET  /analytics/user/{user_id}/history  — paginated request history
    GET  /analytics/leaderboard             — top users by token usage
    GET  /analytics/models                  — aggregate stats per model across all users
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from fastapi import Request
from database import SessionLocal, QueryAnalytic, UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# ── pricing table (mirrors main.py _MODEL_PRICING) ───────────────────────────
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemma":    {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
    "gpt4":     {"input": 1.10 / 1_000_000, "output": 4.40 / 1_000_000},
    "gpt5nano": {"input": 1.10 / 1_000_000, "output": 4.40 / 1_000_000},
    "openai":   {"input": 1.10 / 1_000_000, "output": 4.40 / 1_000_000},
}
USD_TO_INR = 85.0


def _price(model: str, input_tokens: int, output_tokens: int) -> dict:
    p = _MODEL_PRICING.get(model.lower(), _MODEL_PRICING["gemma"])
    usd = input_tokens * p["input"] + output_tokens * p["output"]
    return {"usd": round(usd, 8), "inr": round(usd * USD_TO_INR, 6)}


# ── DB dependency ─────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── response schemas ──────────────────────────────────────────────────────────
class ModelUsage(BaseModel):
    model: str
    requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    cost_inr: float


class UserProfile(BaseModel):
    user_id: str
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    total_cost_inr: float
    input_cost_usd: float
    output_cost_usd: float
    models_used: list[ModelUsage]
    first_seen: Optional[str]
    last_seen: Optional[str]


class RequestLog(BaseModel):
    id: str
    session_id: str
    model_used: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    cost_inr: float
    latency_ms: float
    has_attachment: bool
    attachment_type: Optional[str]
    query_preview: Optional[str]
    created_at: Optional[str]


class PaginatedHistory(BaseModel):
    user_id: str
    page: int
    page_size: int
    total: int
    results: list[RequestLog]


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    total_tokens: int
    total_requests: int
    total_cost_usd: float


class ModelAggregate(BaseModel):
    model: str
    total_users: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float


# ── helpers ───────────────────────────────────────────────────────────────────

def _ts(val) -> Optional[str]:
    """Safely convert a datetime or string to ISO string."""
    if val is None:
        return None
    return val.isoformat() if hasattr(val, "isoformat") else str(val)


def _model_breakdown(db: Session, user_id: str) -> list[ModelUsage]:
    rows = (
        db.query(
            QueryAnalytic.model_used,
            func.count(QueryAnalytic.query_id).label("requests"),
            func.coalesce(func.sum(QueryAnalytic.tokens_in), 0).label("input_tokens"),
            func.coalesce(func.sum(QueryAnalytic.tokens_out), 0).label("output_tokens"),
        )
        .filter(QueryAnalytic.user_id == user_id)
        .group_by(QueryAnalytic.model_used)
        .all()
    )

    result = []
    for row in rows:
        cost = _price(row.model_used, row.input_tokens, row.output_tokens)
        result.append(ModelUsage(
            model=row.model_used,
            requests=row.requests,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            total_tokens=row.input_tokens + row.output_tokens,
            cost_usd=cost["usd"],
            cost_inr=cost["inr"],
        ))
    return result


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/user/{user_id}", response_model=UserProfile)
def user_profile(user_id: str, db: Session = Depends(get_db)):
    """
    Full analytics profile for a single user.

    Returns:
      - Identity (user_id, first/last seen)
      - Total input tokens, output tokens, requests
      - Total cost split by input vs output (USD + INR)
      - Per-model breakdown: which models used, how many tokens, how much cost
    """
    totals = (
        db.query(
            func.count(QueryAnalytic.query_id).label("requests"),
            func.coalesce(func.sum(QueryAnalytic.tokens_in),  0).label("input_tokens"),
            func.coalesce(func.sum(QueryAnalytic.tokens_out), 0).label("output_tokens"),
            func.min(QueryAnalytic.timestamp).label("first_seen"),
            func.max(QueryAnalytic.timestamp).label("last_seen"),
        )
        .filter(QueryAnalytic.user_id == user_id)
        .first()
    )

    if not totals or totals.requests == 0:
        raise HTTPException(status_code=404, detail=f"No data found for user '{user_id}'")

    models = _model_breakdown(db, user_id)

    total_input  = totals.input_tokens
    total_output = totals.output_tokens

    # Aggregate cost across all models correctly
    total_cost_usd = sum(m.cost_usd for m in models)
    total_cost_inr = round(total_cost_usd * USD_TO_INR, 6)

    # Input-only and output-only cost breakdown
    input_cost_usd  = sum(
        m.input_tokens * _MODEL_PRICING.get(m.model.lower(), _MODEL_PRICING["gemma"])["input"]
        for m in models
    )
    output_cost_usd = sum(
        m.output_tokens * _MODEL_PRICING.get(m.model.lower(), _MODEL_PRICING["gemma"])["output"]
        for m in models
    )

    return UserProfile(
        user_id=user_id,
        total_requests=totals.requests,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_input + total_output,
        total_cost_usd=round(total_cost_usd, 8),
        total_cost_inr=round(total_cost_inr, 6),
        input_cost_usd=round(input_cost_usd, 8),
        output_cost_usd=round(output_cost_usd, 8),
        models_used=models,
        first_seen=_ts(totals.first_seen),
        last_seen=_ts(totals.last_seen),
    )


@router.get("/user/{user_id}/history", response_model=PaginatedHistory)
def user_history(
    user_id:   str,
    page:      int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    model:     Optional[str] = Query(default=None, description="Filter by model name"),
    db:        Session = Depends(get_db),
):
    """
    Paginated request-by-request history for a user.
    Optionally filter by model (e.g. ?model=gpt4).
    Each row shows: model, tokens in/out, cost, latency, query preview.
    """
    query = db.query(QueryAnalytic).filter(QueryAnalytic.user_id == user_id)
    if model:
        query = query.filter(QueryAnalytic.model_used == model.lower())

    total = query.count()
    rows  = (
        query.order_by(desc(QueryAnalytic.timestamp))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []
    for row in rows:
        cost = _price(row.model_used, row.tokens_in or 0, row.tokens_out or 0)
        results.append(RequestLog(
            id=row.query_id,
            session_id=row.session_id or "",
            model_used=row.model_used,
            input_tokens=row.tokens_in or 0,
            output_tokens=row.tokens_out or 0,
            total_tokens=(row.tokens_in or 0) + (row.tokens_out or 0),
            cost_usd=cost["usd"],
            cost_inr=cost["inr"],
            latency_ms=round(row.latency_ms or 0, 2),
            has_attachment=bool(row.has_attachment),
            attachment_type=row.attachment_type,
            query_preview=row.query_text,
            created_at=_ts(row.timestamp),
        ))

    return PaginatedHistory(
        user_id=user_id,
        page=page,
        page_size=page_size,
        total=total,
        results=results,
    )


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
def leaderboard(
    top: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Top N users ranked by total token consumption.
    Useful for identifying heavy users or abuse patterns.
    """
    rows = (
        db.query(
            QueryAnalytic.user_id,
            func.count(QueryAnalytic.query_id).label("requests"),
            func.coalesce(func.sum(QueryAnalytic.tokens_in),  0).label("input_tokens"),
            func.coalesce(func.sum(QueryAnalytic.tokens_out), 0).label("output_tokens"),
        )
        .group_by(QueryAnalytic.user_id)
        .order_by(desc(func.sum(QueryAnalytic.tokens_in) + func.sum(QueryAnalytic.tokens_out)))
        .limit(top)
        .all()
    )

    result = []
    for rank, row in enumerate(rows, start=1):
        models_used = _model_breakdown(db, row.user_id)
        total_cost  = sum(m.cost_usd for m in models_used)
        result.append(LeaderboardEntry(
            rank=rank,
            user_id=row.user_id,
            total_tokens=row.input_tokens + row.output_tokens,
            total_requests=row.requests,
            total_cost_usd=round(total_cost, 8),
        ))
    return result


@router.get("/models", response_model=list[ModelAggregate])
def model_aggregates(db: Session = Depends(get_db)):
    """
    Aggregate usage stats per model across ALL users.
    Shows which model is most used, total tokens, total estimated cost.
    """
    rows = (
        db.query(
            QueryAnalytic.model_used,
            func.count(func.distinct(QueryAnalytic.user_id)).label("total_users"),
            func.count(QueryAnalytic.query_id).label("total_requests"),
            func.coalesce(func.sum(QueryAnalytic.tokens_in),  0).label("total_input"),
            func.coalesce(func.sum(QueryAnalytic.tokens_out), 0).label("total_output"),
        )
        .group_by(QueryAnalytic.model_used)
        .order_by(desc(func.sum(QueryAnalytic.tokens_in) + func.sum(QueryAnalytic.tokens_out)))
        .all()
    )

    result = []
    for row in rows:
        cost = _price(row.model_used, row.total_input, row.total_output)
        result.append(ModelAggregate(
            model=row.model_used,
            total_users=row.total_users,
            total_requests=row.total_requests,
            total_input_tokens=row.total_input,
            total_output_tokens=row.total_output,
            total_cost_usd=cost["usd"],
        ))
    return result


# ── Admin: all users ──────────────────────────────────────────────────────────

class AdminUserModel(BaseModel):
    user_id:            str
    display_name:       str
    total_requests:     int
    total_tokens_in:    int
    total_tokens_out:   int
    total_cost_usd:     float
    total_cost_inr:     float
    last_seen:          Optional[str]
    models:             list[ModelUsage]


@router.get("/users", response_model=list[AdminUserModel])
def all_users(request: Request, db: Session = Depends(get_db)):
    """
    All users with aggregated stats and per-model breakdown.
    Used by the admin dashboard. Admin-only.
    """
    from admin_auth import require_admin
    require_admin(request)

    # Query all registered users from user_profiles (includes users with 0 chats)
    profiles = db.query(UserProfile).order_by(desc(UserProfile.last_seen)).all()

    result = []
    for profile in profiles:
        # Aggregate chat stats for this user (may be zero if they never chatted)
        stats = (
            db.query(
                func.count(QueryAnalytic.query_id).label("requests"),
                func.coalesce(func.sum(QueryAnalytic.tokens_in),  0).label("tokens_in"),
                func.coalesce(func.sum(QueryAnalytic.tokens_out), 0).label("tokens_out"),
            )
            .filter(QueryAnalytic.user_id == profile.user_id)
            .first()
        )
        models = _model_breakdown(db, profile.user_id)
        total_cost_usd = sum(m.cost_usd for m in models)
        result.append(AdminUserModel(
            user_id=profile.user_id,
            display_name=profile.display_name or profile.user_id,
            total_requests=stats.requests if stats else 0,
            total_tokens_in=stats.tokens_in if stats else 0,
            total_tokens_out=stats.tokens_out if stats else 0,
            total_cost_usd=round(total_cost_usd, 8),
            total_cost_inr=round(total_cost_usd * USD_TO_INR, 6),
            last_seen=_ts(profile.last_seen),
            models=models,
        ))
    return result