"""
admin_auth.py — Admin access helpers
-------------------------------------
Reads ADMIN_EMAILS from .env and exposes:
  - is_admin(request)  → bool
  - require_admin(request) → raises 403 if not admin
  - GET /admin/check  → {"is_admin": true/false}
"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import SessionLocal, upsert_user


class RegisterBody(BaseModel):
    organization: Optional[str] = None
    role: Optional[str] = None

router = APIRouter(prefix="/admin", tags=["Admin"])


def _admin_emails() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_admin(request: Request) -> bool:
    user = getattr(request.state, "user", None)
    if not user:
        return False
    email = (user.get("email") or "").lower()
    return email in _admin_emails()


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required.")


@router.get("/check")
def check_admin(request: Request):
    user  = getattr(request.state, "user", None)
    email = (user.get("email") or "").lower() if user else ""
    return {"is_admin": is_admin(request), "email": email, "admin_list": list(_admin_emails())}


@router.post("/register")
def register_user(request: Request, body: RegisterBody = RegisterBody()):
    """Called by the frontend on every login to ensure the user exists in user_profiles."""
    user = getattr(request.state, "user", None)
    if not user or not user.get("uid"):
        raise HTTPException(status_code=401, detail="Authentication required.")
    uid          = user["uid"]
    display_name = user.get("name") or user.get("email") or None
    db = SessionLocal()
    try:
        upsert_user(
            db, uid,
            display_name=display_name,
            organization=body.organization or None,
            role=body.role or None,
        )
    finally:
        db.close()
    return {"registered": True, "user_id": uid}
