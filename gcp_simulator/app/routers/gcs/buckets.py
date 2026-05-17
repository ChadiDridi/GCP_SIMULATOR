import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.gcs import Bucket
from gcp_simulator.app.schemas.gcs import BucketCreate, BucketResponse

router = APIRouter()


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.get("/storage/v1/b")
async def list_buckets(
    request: Request,
    project: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    project_id = project or request.state.project_id
    result = await db.execute(select(Bucket).where(Bucket.project_id == project_id))
    buckets = result.scalars().all()
    base = _base_url(request)
    return {
        "kind": "storage#buckets",
        "items": [BucketResponse.from_orm(b, base).model_dump() for b in buckets],
    }


@router.post("/storage/v1/b", status_code=200)
async def create_bucket(
    request: Request,
    body: BucketCreate,
    db: AsyncSession = Depends(get_db),
):
    project_id = request.state.project_id
    existing = await db.execute(select(Bucket).where(Bucket.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Bucket {body.name} already exists")

    bucket = Bucket(
        id=uuid.uuid4(),
        project_id=project_id,
        name=body.name,
        location=body.location,
        storage_class=body.storageClass,
        labels=body.labels,
        created_at=datetime.now(timezone.utc),
    )
    db.add(bucket)
    await db.flush()
    return BucketResponse.from_orm(bucket, _base_url(request)).model_dump()


@router.get("/storage/v1/b/{bucket}")
async def get_bucket(bucket: str, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Bucket).where(Bucket.name == bucket))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail=f"Bucket {bucket} not found")
    return BucketResponse.from_orm(b, _base_url(request)).model_dump()


@router.patch("/storage/v1/b/{bucket}")
async def update_bucket(
    bucket: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Bucket).where(Bucket.name == bucket))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail=f"Bucket {bucket} not found")

    body = await request.json()
    if "labels" in body:
        b.labels = body["labels"]
    if "location" in body:
        b.location = body["location"]
    if "storageClass" in body:
        b.storage_class = body["storageClass"]
    if "versioning" in body:
        b.versioning = body["versioning"].get("enabled", False)
    await db.flush()
    return BucketResponse.from_orm(b, _base_url(request)).model_dump()


@router.delete("/storage/v1/b/{bucket}", status_code=204)
async def delete_bucket(bucket: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Bucket).where(Bucket.name == bucket))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail=f"Bucket {bucket} not found")
    await db.execute(delete(Bucket).where(Bucket.name == bucket))
