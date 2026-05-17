import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.auth import ServiceAccount, Token
from gcp_simulator.app.schemas.auth import TokenResponse

router = APIRouter(tags=["oauth2"])

_JOSE_AVAILABLE = True
try:
    from jose import jwt, JWTError
except ImportError:
    _JOSE_AVAILABLE = False


@router.post("/token", response_model=TokenResponse)
@router.post("/o/oauth2/token", response_model=TokenResponse)
async def issue_token(
    grant_type: str = Form(...),
    assertion: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if grant_type == "urn:ietf:params:oauth:grant-type:jwt-bearer":
        if not assertion:
            raise HTTPException(status_code=400, detail="assertion required")
        return await _handle_jwt_assertion(assertion, db)

    # Allow client_credentials for convenience in dev
    if grant_type == "client_credentials":
        return _mint_dev_token()

    raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")


async def _handle_jwt_assertion(assertion: str, db: AsyncSession) -> TokenResponse:
    if not _JOSE_AVAILABLE:
        # Fallback: skip verification, extract project from claims
        import base64, json as _json
        try:
            parts = assertion.split(".")
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = _json.loads(base64.urlsafe_b64decode(padded))
            project_id = claims.get("aud", "local-dev").split("/")[-1] if "/" in claims.get("aud", "") else "local-dev"
            email = claims.get("iss", "unknown@local-dev.iam.gserviceaccount.com")
        except Exception:
            project_id = "local-dev"
            email = "unknown@local-dev.iam.gserviceaccount.com"
        return await _store_and_return_token(project_id, email, db)

    # Decode header to find key_id
    try:
        header = jwt.get_unverified_header(assertion)
        key_id = header.get("kid")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}")

    # Look up service account by key_id
    result = await db.execute(select(ServiceAccount).where(ServiceAccount.key_id == key_id))
    sa = result.scalar_one_or_none()

    if sa:
        try:
            claims = jwt.decode(assertion, sa.public_key_pem, algorithms=["RS256"], options={"verify_aud": False})
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"JWT verification failed: {e}")
        project_id = sa.project_id
        email = sa.email
    else:
        # Unknown key — accept in dev mode by skipping signature check
        try:
            claims = jwt.decode(assertion, options={"verify_signature": False, "verify_aud": False})
            project_id = claims.get("sub", "local-dev").split("@")[1].split(".")[0] if "@" in claims.get("sub", "") else "local-dev"
            email = claims.get("iss", "unknown@local-dev.iam.gserviceaccount.com")
        except JWTError:
            project_id = "local-dev"
            email = "unknown@local-dev.iam.gserviceaccount.com"

    return await _store_and_return_token(project_id, email, db)


async def _store_and_return_token(project_id: str, email: str, db: AsyncSession) -> TokenResponse:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    db_token = Token(
        id=uuid.uuid4(),
        token_hash=token_hash,
        project_id=project_id,
        service_account_email=email,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(db_token)
    await db.flush()

    return TokenResponse(access_token=raw_token)


def _mint_dev_token() -> TokenResponse:
    return TokenResponse(access_token=secrets.token_urlsafe(48))


@router.get("/oauth2/v1/certs")
async def get_certs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ServiceAccount))
    accounts = result.scalars().all()
    keys = {sa.key_id: sa.public_key_pem for sa in accounts}
    return keys
