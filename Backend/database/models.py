from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class UserProfile(Base):
    """
    Anonymous user identity anchored to a browser localStorage UUID.
    No login required — created on first request, recognised on every subsequent one.
    """
    __tablename__ = "user_profiles"

    user_id      = Column(String(64),  primary_key=True)
    display_name = Column(String(64),  nullable=True)
    organization = Column(String(128), nullable=True)
    role         = Column(String(64),  nullable=True)
    created_at   = Column(DateTime,    nullable=False, default=datetime.utcnow)
    last_seen    = Column(DateTime,    nullable=False, default=datetime.utcnow)


class ChatSession(Base):
    """
    One browser tab / conversation = one session.
    Links a session_id (from localStorage) to a user_id.
    """
    __tablename__ = "chat_sessions"

    session_id  = Column(String(64), primary_key=True)
    user_id     = Column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_active = Column(DateTime, nullable=False, default=datetime.utcnow)
    # JSON array of text chunks from the last uploaded PDF.
    # Persisted so follow-up questions survive server restarts.
    pdf_chunks  = Column(Text, nullable=True)


class QueryAnalytic(Base):
    """
    One row per LLM call.  Captures full cost/perf breakdown for every query.
    """
    __tablename__ = "query_analytics"

    query_id        = Column(String(64),  primary_key=True)
    session_id      = Column(
        String(64),
        ForeignKey("chat_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id         = Column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    model_used      = Column(String(32),  nullable=False)
    tokens_in       = Column(Integer,     nullable=False)           # full prompt context
    tokens_out      = Column(Integer,     nullable=False)           # completion only
    tokens_attach   = Column(Integer,     nullable=False, default=0)  # file content tokens
    latency_ms      = Column(Float,       nullable=False)
    cost_usd        = Column(Float,       nullable=False)
    cost_inr        = Column(Float,       nullable=False)
    timestamp       = Column(DateTime,    nullable=False, default=datetime.utcnow)
    query_text      = Column(String(500), nullable=True)            # first 500 chars of user message
    has_attachment  = Column(Boolean,     nullable=False, default=False)
    attachment_type = Column(String(16),  nullable=True)            # 'image' | 'pdf' | None


class ApiUsage(Base):
    """
    One row per call to the public /v1/generate endpoint.
    External applications authenticate with a shared API key and identify
    themselves via the X-App-Name header. Captures full cost/token breakdown
    so usage can be attributed per calling application.
    """
    __tablename__ = "api_usage"

    usage_id    = Column(String(64),  primary_key=True)   # uuid4
    application = Column(String(128), nullable=False)     # from X-App-Name header
    query_text  = Column(String(500), nullable=True)      # first 500 chars of message
    model_used  = Column(String(32),  nullable=False)
    tokens_in   = Column(Integer,     nullable=False)
    tokens_out  = Column(Integer,     nullable=False)
    cost_usd    = Column(Float,       nullable=False)
    cost_inr    = Column(Float,       nullable=False)
    latency_ms  = Column(Float,       nullable=False)
    timestamp   = Column(DateTime,    nullable=False, default=datetime.utcnow)


class ApiKey(Base):
    """One API key per user. Raw key shown once; only SHA-256 hash stored."""
    __tablename__ = "api_keys"

    id         = Column(Integer,    primary_key=True, autoincrement=True)
    user_id    = Column(String(64), nullable=False, unique=True)
    key_prefix = Column(String(16), nullable=False)   # first 12 chars for display
    key_hash   = Column(String(64), nullable=False)   # SHA-256 hex digest
    created_at = Column(DateTime,   nullable=False, default=datetime.utcnow)
    last_used  = Column(DateTime,   nullable=True)


class AgentRun(Base):
    """
    One row per agent run through the /v1/agent/run proxy.
    Tracks the full lifecycle: model, tokens, cost, tools, and conversation.
    """
    __tablename__ = "agent_runs"

    run_id        = Column(String(64),  primary_key=True)
    user_id       = Column(String(64),  nullable=False)        # Firebase UID of key owner
    agent_name    = Column(String(128), nullable=False)
    model         = Column(String(64),  nullable=False)
    query         = Column(Text,        nullable=True)          # first user message (up to 1000 chars)
    response      = Column(Text,        nullable=True)          # final assistant response
    status        = Column(String(16),  nullable=False, default="running")  # running|tool_pending|completed|error
    tokens_in     = Column(Integer,     nullable=False, default=0)
    tokens_out    = Column(Integer,     nullable=False, default=0)
    cost_usd      = Column(Float,       nullable=False, default=0.0)
    cost_inr      = Column(Float,       nullable=False, default=0.0)
    latency_ms    = Column(Float,       nullable=False, default=0.0)
    tools_defined = Column(Text,        nullable=True)          # JSON: OpenAI tool schemas passed by agent
    tools_called  = Column(Text,        nullable=True)          # JSON: [{name, input}] actually invoked
    messages      = Column(Text,        nullable=True)          # JSON: full conversation for multi-turn
    error         = Column(Text,        nullable=True)
    started_at    = Column(DateTime,    nullable=False, default=datetime.utcnow)
    finished_at   = Column(DateTime,    nullable=True)
