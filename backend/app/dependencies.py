"""Supabase JWT authentication.

Every protected endpoint resolves the caller's identity here. The frontend
signs users in with Supabase Auth and sends the access token as
``Authorization: Bearer <token>``; we verify the signature (HS256) with the
project's JWT secret and use the token's ``sub`` claim (the stable Supabase
user UUID) as the ``user_id`` that enrollments, embeddings, and sessions are
keyed by.

Local development without Supabase: set ``DEV_NO_AUTH=1`` in the backend
``.env``. Auth is then skipped and the caller identity comes from the
``X-User-Id`` header (default ``demo_user``). This is strictly a dev
convenience — it is OFF by default and must never be enabled in production.
"""
import logging

from fastapi import Header, HTTPException

from .config import get_settings

logger = logging.getLogger(__name__)


def _dev_bypass_user(x_user_id: str | None) -> str:
    user_id = (x_user_id or "").strip() or "demo_user"
    logger.warning(
        "DEV_NO_AUTH is enabled - accepting unauthenticated request as '%s'. "
        "Never enable this in production.",
        user_id,
    )
    return user_id


def get_user_id_from_token(token: str | None, x_user_id: str | None = None) -> str:
    """Verify a Supabase access token and return the caller's user id.

    Raises:
        HTTPException(401): Missing, malformed, or invalid/expired token.
        HTTPException(500): Server misconfigured (no JWT secret and no dev bypass).
    """
    settings = get_settings()

    if settings.dev_no_auth:
        return _dev_bypass_user(x_user_id)

    if not token or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header. Expected 'Bearer <Supabase access token>'.",
        )

    if not settings.supabase_jwt_secret:
        logger.error(
            "SUPABASE_JWT_SECRET is not configured - cannot verify tokens. "
            "Set it in backend/.env (or set DEV_NO_AUTH=1 for local development only)."
        )
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: SUPABASE_JWT_SECRET is not set.",
        )

    try:
        import jwt

        payload = jwt.decode(
            token.strip(),
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except ImportError:
        logger.error("PyJWT is not installed - cannot verify tokens.")
        raise HTTPException(status_code=500, detail="Server misconfiguration: JWT support missing.")
    except Exception as e:
        logger.info("Rejecting request with invalid/expired token: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token: missing 'sub' claim.")
    return str(user_id)


async def verify_token(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    """FastAPI dependency: resolve the caller's Supabase user id from the
    ``Authorization: Bearer <token>`` header."""
    scheme, _, token = (authorization or "").partition(" ")
    if not authorization or scheme.lower() != "bearer" or not token:
        # Let the shared helper produce the canonical 401 (or dev bypass).
        return get_user_id_from_token(None, x_user_id)
    return get_user_id_from_token(token, x_user_id)
