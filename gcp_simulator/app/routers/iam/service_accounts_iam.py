import base64
import json
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.auth import ServiceAccount

router = APIRouter()


def _sa_response(sa: ServiceAccount) -> dict:
    return {
        "name": f"projects/{sa.project_id}/serviceAccounts/{sa.email}",
        "projectId": sa.project_id,
        "uniqueId": sa.key_id,
        "email": sa.email,
        "displayName": sa.email.split("@")[0],
        "oauth2ClientId": sa.key_id,
    }


@router.get("/v1/projects/{project_id}/serviceAccounts")
async def list_service_accounts(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceAccount).where(ServiceAccount.project_id == project_id)
    )
    accounts = result.scalars().all()
    return {"accounts": [_sa_response(a) for a in accounts]}


@router.get("/v1/projects/{project_id}/serviceAccounts/{email}")
async def get_service_account(
    project_id: str,
    email: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceAccount).where(
            ServiceAccount.project_id == project_id,
            ServiceAccount.email == email,
        )
    )
    sa = result.scalar_one_or_none()
    if not sa:
        raise HTTPException(status_code=404, detail=f"ServiceAccount {email} not found")
    return _sa_response(sa)


@router.delete(
    "/v1/projects/{project_id}/serviceAccounts/{email}",
    status_code=204,
)
async def delete_service_account(
    project_id: str,
    email: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceAccount).where(
            ServiceAccount.project_id == project_id,
            ServiceAccount.email == email,
        )
    )
    sa = result.scalar_one_or_none()
    if not sa:
        raise HTTPException(status_code=404, detail=f"ServiceAccount {email} not found")
    await db.execute(
        delete(ServiceAccount).where(
            ServiceAccount.project_id == project_id,
            ServiceAccount.email == email,
        )
    )


@router.post("/v1/projects/{project_id}/serviceAccounts/{email}/keys")
async def create_service_account_key(
    project_id: str,
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate a new RSA key pair, store the public key on the SA, and return the private key."""
    result = await db.execute(
        select(ServiceAccount).where(
            ServiceAccount.project_id == project_id,
            ServiceAccount.email == email,
        )
    )
    sa = result.scalar_one_or_none()
    if not sa:
        raise HTTPException(status_code=404, detail=f"ServiceAccount {email} not found")

    # Generate new RSA key pair
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    key_id = str(uuid.uuid4()).replace("-", "")[:40]

    # Update the stored public key and key_id
    sa.public_key_pem = public_pem
    sa.key_id = key_id
    await db.flush()

    # Build a JSON service-account key file (standard GCP format)
    key_file = {
        "type": "service_account",
        "project_id": project_id,
        "private_key_id": key_id,
        "private_key": private_pem,
        "client_email": email,
        "client_id": key_id,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    encoded = base64.b64encode(json.dumps(key_file).encode()).decode()

    return {
        "name": f"projects/{project_id}/serviceAccounts/{email}/keys/{key_id}",
        "privateKeyType": "TYPE_GOOGLE_CREDENTIALS_FILE",
        "keyAlgorithm": "KEY_ALG_RSA_2048",
        "privateKeyData": encoded,
        "publicKeyData": base64.b64encode(public_pem.encode()).decode(),
        "validAfterTime": datetime.now(timezone.utc).isoformat(),
        "validBeforeTime": None,
        "keyOrigin": "GOOGLE_PROVIDED",
    }
