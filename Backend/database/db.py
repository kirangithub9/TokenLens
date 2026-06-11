import hashlib
import json
import logging
import os
import secrets
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, UserProfile, ChatSession, QueryAnalytic, ApiUsage, ApiKey, AgentRun

logger = logging.getLogger(__name__)

# ── connection setup ──────────────────────────────────────────────────────────

_raw_url = os.getenv("DATABASE_URL", "sqlite:///./gemma_chat.db")

# Supabase (and some other providers) return "postgres://" which SQLAlchemy 2.0
# no longer accepts — it requires "postgresql://"
DATABASE_URL = _raw_url.replace("postgres://", "postgresql://", 1) if _raw_url.startswith("postgres://") else _raw_url

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite + multi-thread safety
        pool_pre_ping=True,
    )
else:
    # PostgreSQL / Supabase
    # pool_size + max_overflow kept modest for Supabase free tier (max 60 direct connections)
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # recycles stale connections transparently
        pool_size=5,
        max_overflow=10,
    )
    logger.info("Using PostgreSQL backend: %s", DATABASE_URL.split("@")[-1])  # log host only, not password

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables if they don't exist yet. Safe to call on every startup."""
    Base.metadata.create_all(engine)
    _run_migrations()
    backend = "SQLite" if _is_sqlite else "PostgreSQL"
    logger.info("Database tables ready (%s).", backend)


def _run_migrations() -> None:
    """
    Apply additive schema changes that create_all() won't handle on existing tables.
    Each migration is idempotent — safe to run on every startup.
    """
    try:
        with engine.connect() as conn:
            if _is_sqlite:
                # SQLite: check PRAGMA, add only if missing
                existing = {r[1] for r in conn.execute(text("PRAGMA table_info(chat_sessions)"))}
                if "pdf_chunks" not in existing:
                    conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN pdf_chunks TEXT"))
                    conn.commit()
                    logger.info("Migration: added pdf_chunks column (SQLite).")
            else:
                # PostgreSQL: IF NOT EXISTS handles idempotency natively
                conn.execute(text(
                    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS pdf_chunks TEXT"
                ))
                conn.commit()
    except Exception as exc:
        logger.warning("Migration skipped (non-fatal): %s", exc)


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def upsert_user(db: Session, user_id: str, display_name: str | None = None) -> UserProfile:
    """Create user on first visit; update last_seen and name on every subsequent request."""
    now  = datetime.utcnow()
    user = db.get(UserProfile, user_id)
    if user is None:
        name = display_name or f"User-{user_id[-6:].upper()}"
        user = UserProfile(
            user_id      = user_id,
            display_name = name,
            created_at   = now,
            last_seen    = now,
        )
        db.add(user)
        logger.info("New user created: %s (%s)", user_id, name)
    else:
        user.last_seen = now
        if display_name:
            user.display_name = display_name
    db.commit()
    return user


def upsert_session(db: Session, session_id: str, user_id: str) -> ChatSession:
    """Create session row on first message; bump last_active on every request."""
    now  = datetime.utcnow()
    sess = db.get(ChatSession, session_id)
    if sess is None:
        sess = ChatSession(
            session_id  = session_id,
            user_id     = user_id,
            created_at  = now,
            last_active = now,
        )
        db.add(sess)
        logger.info("New session created: %s (user=%s)", session_id, user_id)
    else:
        sess.last_active = now
    db.commit()
    return sess


def save_pdf_chunks(db: Session, session_id: str, chunks: list[str]) -> None:
    """Persist PDF text chunks for a session so they survive server restarts."""
    sess = db.get(ChatSession, session_id)
    if sess is None:
        logger.warning("save_pdf_chunks: session %s not found", session_id)
        return
    sess.pdf_chunks = json.dumps(chunks)
    db.commit()
    logger.info("Saved %d PDF chunks to DB for session %s", len(chunks), session_id)


def load_pdf_chunks(db: Session, session_id: str) -> list[str] | None:
    """Load PDF text chunks from DB. Returns None if none saved."""
    sess = db.get(ChatSession, session_id)
    if sess is None or not sess.pdf_chunks:
        return None
    try:
        return json.loads(sess.pdf_chunks)
    except Exception as e:
        logger.error("Failed to deserialize pdf_chunks for %s: %s", session_id, e)
        return None


def log_query(
    db:              Session,
    *,
    session_id:      str,
    user_id:         str,
    model_used:      str,
    tokens_in:       int,
    tokens_out:      int,
    tokens_attach:   int,
    latency_ms:      float,
    cost_usd:        float,
    cost_inr:        float,
    query_text:      str | None = None,
    has_attachment:  bool       = False,
    attachment_type: str | None = None,
) -> QueryAnalytic:
    record = QueryAnalytic(
        query_id        = str(uuid.uuid4()),
        session_id      = session_id,
        user_id         = user_id,
        model_used      = model_used,
        tokens_in       = tokens_in,
        tokens_out      = tokens_out,
        tokens_attach   = tokens_attach,
        latency_ms      = round(latency_ms, 2),
        cost_usd        = cost_usd,
        cost_inr        = cost_inr,
        timestamp       = datetime.utcnow(),
        query_text      = (query_text or "")[:500] or None,
        has_attachment  = has_attachment,
        attachment_type = attachment_type,
    )
    db.add(record)
    db.commit()
    return record


def verify_api_key(db: Session, raw_key: str) -> str | None:
    """Hash raw key, look up in api_keys, update last_used. Returns user_id or None."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    row = db.query(ApiKey).filter_by(key_hash=key_hash).first()
    if not row:
        return None
    row.last_used = datetime.utcnow()
    db.commit()
    return row.user_id


def create_api_key(db: Session, user_id: str) -> str:
    """Generate a new API key for the user, replacing any existing one. Returns raw key once."""
    existing = db.query(ApiKey).filter_by(user_id=user_id).first()
    if existing:
        db.delete(existing)
        db.flush()
    raw = "tl-" + secrets.token_urlsafe(32)
    record = ApiKey(
        user_id    = user_id,
        key_prefix = raw[:12],
        key_hash   = hashlib.sha256(raw.encode()).hexdigest(),
        created_at = datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    return raw


def get_api_key_info(db: Session, user_id: str):
    """Return the ApiKey row for the user, or None."""
    return db.query(ApiKey).filter_by(user_id=user_id).first()


def revoke_api_key(db: Session, user_id: str) -> None:
    """Delete the user's API key."""
    row = db.query(ApiKey).filter_by(user_id=user_id).first()
    if row:
        db.delete(row)
        db.commit()


def create_agent_run(
    db: Session,
    *,
    run_id:       str,
    user_id:      str,
    agent_name:   str,
    model:        str,
    query:        str | None,
    tools_defined: str | None,
    messages:     str,
) -> AgentRun:
    record = AgentRun(
        run_id        = run_id,
        user_id       = user_id,
        agent_name    = agent_name,
        model         = model,
        query         = (query or "")[:1000] or None,
        tools_defined = tools_defined,
        messages      = messages,
        started_at    = datetime.utcnow(),
        status        = "running",
    )
    db.add(record)
    db.commit()
    return record


def set_agent_run_progress(
    db: Session,
    run_id: str,
    *,
    status:       str,
    tokens_in:    int,
    tokens_out:   int,
    cost_usd:     float,
    cost_inr:     float,
    latency_ms:   float,
    tools_called: str | None = None,
    messages:     str | None = None,
    response:     str | None = None,
    error:        str | None = None,
) -> None:
    row = db.query(AgentRun).filter_by(run_id=run_id).first()
    if not row:
        return
    row.status     = status
    row.tokens_in  = tokens_in
    row.tokens_out = tokens_out
    row.cost_usd   = cost_usd
    row.cost_inr   = cost_inr
    row.latency_ms = round(latency_ms, 2)
    if tools_called is not None:
        row.tools_called = tools_called
    if messages is not None:
        row.messages = messages
    if response is not None:
        row.response = response
    if error is not None:
        row.error = error
    if status in ("completed", "error"):
        row.finished_at = datetime.utcnow()
    db.commit()


def get_agent_run(db: Session, run_id: str) -> AgentRun | None:
    return db.query(AgentRun).filter_by(run_id=run_id).first()


def get_agent_runs_for_user(db: Session, user_id: str, limit: int = 100) -> list[AgentRun]:
    return (
        db.query(AgentRun)
        .filter_by(user_id=user_id)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
        .all()
    )


def log_sdk_agent_run(
    db: Session,
    *,
    user_id:    str,
    agent_name: str,
    model:      str,
    query_text: str | None,
    response_text: str | None,
    tokens_in:  int,
    tokens_out: int,
    cost_usd:   float,
    cost_inr:   float,
    latency_ms: float,
) -> AgentRun:
    """Create a completed AgentRun row from an SDK log call."""
    now = datetime.utcnow()
    record = AgentRun(
        run_id      = str(uuid.uuid4()),
        user_id     = user_id,
        agent_name  = agent_name,
        model       = model,
        query       = (query_text or "")[:1000] or None,
        response    = (response_text or "")[:2000] or None,
        status      = "completed",
        tokens_in   = tokens_in,
        tokens_out  = tokens_out,
        cost_usd    = cost_usd,
        cost_inr    = cost_inr,
        latency_ms  = round(latency_ms, 2),
        started_at  = now,
        finished_at = now,
    )
    db.add(record)
    db.commit()
    return record


def log_api_usage(
    db:          Session,
    *,
    application: str,
    query_text:  str | None,
    model_used:  str,
    tokens_in:   int,
    tokens_out:  int,
    cost_usd:    float,
    cost_inr:    float,
    latency_ms:  float,
) -> ApiUsage:
    """Record one public /v1/generate call, attributed to the calling application."""
    record = ApiUsage(
        usage_id    = str(uuid.uuid4()),
        application = application,
        query_text  = (query_text or "")[:500] or None,
        model_used  = model_used,
        tokens_in   = tokens_in,
        tokens_out  = tokens_out,
        cost_usd    = cost_usd,
        cost_inr    = cost_inr,
        latency_ms  = round(latency_ms, 2),
        timestamp   = datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    return record
