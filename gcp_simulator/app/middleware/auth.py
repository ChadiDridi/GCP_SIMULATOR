import hashlib
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from gcp_simulator.app.config import settings
from gcp_simulator.app.db.engine import AsyncSessionLocal
from gcp_simulator.app.models.auth import Token

# Paths that don't require auth
_EXEMPT_PATHS = {
    "/token",
    "/o/oauth2/token",
    "/oauth2/v1/certs",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            request.state.project_id = settings.project_id
            request.state.service_account = None
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _unauthorized("Missing Bearer token")

        token = auth_header[len("Bearer "):]

        # Dev token shortcut — always valid
        if token == settings.dev_token:
            request.state.project_id = settings.project_id
            request.state.service_account = "dev@local-dev.iam.gserviceaccount.com"
            return await call_next(request)

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Token).where(Token.token_hash == token_hash))
            db_token = result.scalar_one_or_none()

        if not db_token:
            return _unauthorized("Invalid token")

        if db_token.expires_at and db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return _unauthorized("Token expired")

        request.state.project_id = db_token.project_id
        request.state.service_account = db_token.service_account_email
        return await call_next(request)


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": 401,
                "message": detail,
                "status": "UNAUTHENTICATED",
            }
        },
    )
