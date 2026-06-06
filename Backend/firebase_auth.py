"""
firebase_auth.py  —  TokenLens Firebase Authentication
────────────────────────────────────────────────────────
Drop this file into your Backend/ folder.

How it works:
  - Every protected request must carry:  Authorization: Bearer <firebase_id_token>
  - The middleware verifies the token with Firebase Admin SDK
  - Decoded user info (uid, email, name) is injected into Request.state.user
  - Unprotected routes (/, /health, /docs, /openapi.json) are whitelisted

Setup:
  1. pip install firebase-admin
  2. Add Firebase credentials to your .env  (see .env.example additions below)
  3. Drop this file in Backend/
  4. Add 2 lines to main.py  (see HOW_TO_ADD_TO_MAIN.py)
"""

import logging
import os

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ── routes that never require a token ────────────────────────────────────────
PUBLIC_ROUTES = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}

_firebase_app = None


def init_firebase() -> None:
    """
    Initialize Firebase Admin SDK once at startup.
    Reads credentials from environment variables — no JSON file needed.
    """
    global _firebase_app
    if _firebase_app:
        return

    project_id = os.getenv("FIREBASE_PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "FIREBASE_PROJECT_ID not set. Add Firebase credentials to your .env file."
        )

    cert = {
        "type":                        "service_account",
        "project_id":                  project_id,
        "private_key_id":              os.getenv("FIREBASE_PRIVATE_KEY_ID", ""),
        "private_key":                 os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
        "client_email":                os.getenv("FIREBASE_CLIENT_EMAIL", ""),
        "client_id":                   os.getenv("FIREBASE_CLIENT_ID", ""),
        "auth_uri":                    "https://accounts.google.com/o/oauth2/auth",
        "token_uri":                   "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url":        os.getenv("FIREBASE_CLIENT_CERT_URL", ""),
    }

    try:
        cred = credentials.Certificate(cert)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized for project: %s", project_id)
    except Exception as e:
        raise RuntimeError(f"Firebase initialization failed: {e}")


def verify_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token and return the decoded claims.
    Raises firebase_admin.auth.InvalidIdTokenError on failure.
    """
    return auth.verify_id_token(id_token)


# ── middleware ────────────────────────────────────────────────────────────────

class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware — runs before every request.

    On success:  sets request.state.user = {uid, email, name, firebase}
    On failure:  returns 401 JSON immediately, request never reaches the route
    """

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public routes and OPTIONS preflight
        if request.method == "OPTIONS" or request.url.path in PUBLIC_ROUTES:
            return await call_next(request)

        # If Firebase was not initialised (credentials not yet configured), pass through
        if _firebase_app is None:
            logger.warning("Firebase not initialised — skipping auth for %s", request.url.path)
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")

        # API key path — tl- prefixed keys bypass Firebase verification
        if auth_header.startswith("Bearer tl-"):
            raw = auth_header.split(" ", 1)[1].strip()
            from database import SessionLocal, verify_api_key
            db = SessionLocal()
            try:
                uid = verify_api_key(db, raw)
            finally:
                db.close()
            if not uid:
                return JSONResponse(
                    status_code=401,
                    content={"error": "invalid_api_key", "detail": "API key is invalid or has been revoked."},
                )
            request.state.user = {"uid": uid, "email": "", "name": "", "firebase": {}}
            return await call_next(request)
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error":   "unauthorized",
                    "detail":  "Missing Authorization header. Expected: Bearer <firebase_id_token>",
                },
            )

        id_token = auth_header.split(" ", 1)[1].strip()
        if not id_token:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "detail": "Empty token."},
            )

        try:
            decoded = verify_token(id_token)
        except auth.ExpiredIdTokenError:
            return JSONResponse(
                status_code=401,
                content={"error": "token_expired", "detail": "Firebase ID token has expired. Please re-authenticate."},
            )
        except auth.RevokedIdTokenError:
            return JSONResponse(
                status_code=401,
                content={"error": "token_revoked", "detail": "Firebase ID token has been revoked."},
            )
        except auth.InvalidIdTokenError as e:
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_token", "detail": f"Invalid Firebase ID token: {e}"},
            )
        except Exception as e:
            logger.error("Firebase token verification error: %s", e)
            return JSONResponse(
                status_code=401,
                content={"error": "auth_error", "detail": "Could not verify token."},
            )

        # Attach user info to request state — available in every route as:
        #   request.state.user["uid"]
        #   request.state.user["email"]
        #   request.state.user["name"]
        request.state.user = {
            "uid":      decoded.get("uid"),
            "email":    decoded.get("email", ""),
            "name":     decoded.get("name", ""),
            "firebase": decoded.get("firebase", {}),
        }

        logger.debug(
            "Authenticated request: uid=%s  path=%s",
            decoded.get("uid"), request.url.path,
        )

        return await call_next(request)


# ── FastAPI dependency (alternative to middleware) ────────────────────────────
# Use this if you want per-route auth instead of global middleware.
# Example:
#   @app.post("/chat")
#   async def chat(req: ChatRequest, user = Depends(require_auth)):
#       uid = user["uid"]

from fastapi import Header, HTTPException


async def require_auth(authorization: str = Header(...)) -> dict:
    """
    FastAPI dependency — use on individual routes if you prefer
    selective auth instead of the global middleware.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed Authorization header.",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        decoded = verify_token(token)
        return {
            "uid":   decoded.get("uid"),
            "email": decoded.get("email", ""),
            "name":  decoded.get("name", ""),
        }
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")