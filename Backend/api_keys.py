"""
api_keys.py — TokenLens API Key Management
-------------------------------------------
Endpoints:
    POST   /api-keys   — generate a new tl- key (returns raw key once)
    GET    /api-keys   — get current key info (prefix, created_at, last_used)
    DELETE /api-keys   — revoke current key
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import SessionLocal, create_api_key, get_api_key_info, revoke_api_key

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


def _require_user(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if not user or not user.get("uid"):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user["uid"]


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class KeyInfo(BaseModel):
    key_prefix: str
    created_at: str
    last_used: str | None


@router.post("")
def generate_key(request: Request):
    uid = _require_user(request)
    db = SessionLocal()
    try:
        raw = create_api_key(db, uid)
    finally:
        db.close()
    return {"key": raw, "message": "Save this key — it will not be shown again."}


@router.get("", response_model=KeyInfo | None)
def get_key(request: Request):
    uid = _require_user(request)
    db = SessionLocal()
    try:
        row = get_api_key_info(db, uid)
    finally:
        db.close()
    if not row:
        return JSONResponse(status_code=404, content={"detail": "No active API key found."})
    return KeyInfo(
        key_prefix=row.key_prefix,
        created_at=row.created_at.isoformat(),
        last_used=row.last_used.isoformat() if row.last_used else None,
    )


@router.delete("")
def revoke_key(request: Request):
    uid = _require_user(request)
    db = SessionLocal()
    try:
        revoke_api_key(db, uid)
    finally:
        db.close()
    return {"message": "API key revoked successfully."}
