import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.gcs import Bucket, Object, ResumableUpload
from gcp_simulator.app.schemas.gcs import ObjectMetadataResponse

router = APIRouter()


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


async def _require_bucket(bucket: str, db: AsyncSession):
    result = await db.execute(select(Bucket).where(Bucket.name == bucket))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail=f"Bucket {bucket} not found")
    return b


@router.get("/storage/v1/b/{bucket}/o")
async def list_objects(
    bucket: str,
    request: Request,
    prefix: str | None = None,
    delimiter: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    await _require_bucket(bucket, db)
    query = select(Object).where(Object.bucket_name == bucket)
    if prefix:
        query = query.where(Object.name.startswith(prefix))
    result = await db.execute(query)
    objects = result.scalars().all()

    base = _base_url(request)
    items = []
    prefixes: set[str] = set()

    for obj in objects:
        if delimiter:
            remaining = obj.name[len(prefix or ""):]
            idx = remaining.find(delimiter)
            if idx >= 0:
                prefixes.add((prefix or "") + remaining[: idx + 1])
                continue
        items.append(ObjectMetadataResponse.from_orm(obj, base).model_dump())

    resp: dict[str, Any] = {"kind": "storage#objects", "items": items}
    if prefixes:
        resp["prefixes"] = sorted(prefixes)
    return resp


@router.get("/storage/v1/b/{bucket}/o/{object_name:path}")
async def get_object(
    bucket: str,
    object_name: str,
    request: Request,
    alt: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Object).where(Object.bucket_name == bucket, Object.name == object_name)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=f"Object {object_name} not found in {bucket}")

    if alt == "media":
        data = obj.data or b""
        return Response(
            content=data,
            media_type=obj.content_type or "application/octet-stream",
            headers={"Content-Length": str(len(data))},
        )

    return ObjectMetadataResponse.from_orm(obj, _base_url(request)).model_dump()


# Also handle download path
@router.get("/download/storage/v1/b/{bucket}/o/{object_name:path}")
async def download_object(
    bucket: str,
    object_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await get_object(bucket, object_name, request, alt="media", db=db)


@router.delete("/storage/v1/b/{bucket}/o/{object_name:path}", status_code=204)
async def delete_object(
    bucket: str,
    object_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Object).where(Object.bucket_name == bucket, Object.name == object_name)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=f"Object {object_name} not found")
    await db.execute(delete(Object).where(Object.bucket_name == bucket, Object.name == object_name))


@router.patch("/storage/v1/b/{bucket}/o/{object_name:path}")
async def update_object_metadata(
    bucket: str,
    object_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Object).where(Object.bucket_name == bucket, Object.name == object_name)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=f"Object {object_name} not found")

    body = await request.json()
    if "contentType" in body:
        obj.content_type = body["contentType"]
    if "metadata" in body:
        obj.user_metadata = body["metadata"]
    obj.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return ObjectMetadataResponse.from_orm(obj, _base_url(request)).model_dump()


# ── Uploads ──────────────────────────────────────────────────────────────────

@router.post("/upload/storage/v1/b/{bucket}/o")
async def upload_object(
    bucket: str,
    request: Request,
    uploadType: str = "media",
    name: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    await _require_bucket(bucket, db)

    if uploadType == "media":
        return await _simple_upload(bucket, name, request, db)
    elif uploadType == "multipart":
        return await _multipart_upload(bucket, request, db)
    elif uploadType == "resumable":
        return await _initiate_resumable(bucket, name, request, db)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown uploadType: {uploadType}")


async def _simple_upload(bucket: str, name: str | None, request: Request, db: AsyncSession):
    if not name:
        raise HTTPException(status_code=400, detail="name parameter required for simple upload")
    data = await request.body()
    content_type = request.headers.get("Content-Type", "application/octet-stream")
    return await _upsert_object(bucket, name, data, content_type, {}, db, _base_url(request))


async def _multipart_upload(bucket: str, request: Request, db: AsyncSession):
    import email as _email
    content_type_header = request.headers.get("Content-Type", "")
    body = await request.body()

    # Parse boundary from Content-Type header
    boundary = None
    for part in content_type_header.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[len("boundary="):].strip('"')
            break

    if not boundary:
        raise HTTPException(status_code=400, detail="Missing multipart boundary")

    # Split by boundary
    delimiter = f"--{boundary}".encode()
    parts = body.split(delimiter)
    # parts[0] is empty, parts[-1] is "--\r\n"
    metadata_raw = b""
    data_raw = b""
    data_content_type = "application/octet-stream"
    object_name = ""

    for raw_part in parts[1:-1]:
        if raw_part.startswith(b"\r\n"):
            raw_part = raw_part[2:]
        if raw_part.endswith(b"\r\n"):
            raw_part = raw_part[:-2]

        header_end = raw_part.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        headers_raw = raw_part[:header_end].decode(errors="replace")
        part_body = raw_part[header_end + 4:]
        part_ct = ""
        for line in headers_raw.splitlines():
            if line.lower().startswith("content-type:"):
                part_ct = line.split(":", 1)[1].strip()
                break

        if "application/json" in part_ct:
            import json
            try:
                meta = json.loads(part_body)
                object_name = meta.get("name", "")
            except Exception:
                pass
            metadata_raw = part_body
        else:
            data_raw = part_body
            data_content_type = part_ct or "application/octet-stream"

    if not object_name:
        raise HTTPException(status_code=400, detail="Object name missing from metadata part")

    return await _upsert_object(bucket, object_name, data_raw, data_content_type, {}, db, "")


async def _initiate_resumable(bucket: str, name: str | None, request: Request, db: AsyncSession):
    import json
    body = await request.body()
    meta = {}
    if body:
        try:
            meta = json.loads(body)
        except Exception:
            pass

    object_name = name or meta.get("name", "")
    if not object_name:
        raise HTTPException(status_code=400, detail="name parameter required")

    content_type = request.headers.get("X-Upload-Content-Type", meta.get("contentType", "application/octet-stream"))
    total_size_str = request.headers.get("X-Upload-Content-Length")
    total_size = int(total_size_str) if total_size_str else None

    upload_id = secrets.token_urlsafe(32)
    session = ResumableUpload(
        upload_id=upload_id,
        bucket_name=bucket,
        object_name=object_name,
        content_type=content_type,
        total_size=total_size,
        uploaded_bytes=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()

    base = _base_url(request)
    location = f"{base}/upload/storage/v1/b/{bucket}/o?uploadType=resumable&upload_id={upload_id}&name={object_name}"
    return Response(status_code=200, headers={"Location": location})


@router.put("/upload/storage/v1/b/{bucket}/o")
async def upload_resumable_chunk(
    bucket: str,
    request: Request,
    upload_id: str | None = None,
    name: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not upload_id:
        raise HTTPException(status_code=400, detail="upload_id required")

    result = await db.execute(select(ResumableUpload).where(ResumableUpload.upload_id == upload_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found")

    chunk = await request.body()
    existing = session.chunks or b""
    session.chunks = existing + chunk
    session.uploaded_bytes = len(session.chunks)
    await db.flush()

    total = session.total_size
    uploaded = session.uploaded_bytes

    if total is None or uploaded >= total:
        # Finalize
        obj_resp = await _upsert_object(
            session.bucket_name,
            session.object_name,
            session.chunks,
            session.content_type,
            {},
            db,
            _base_url(request),
        )
        await db.execute(
            delete(ResumableUpload).where(ResumableUpload.upload_id == upload_id)
        )
        return obj_resp

    return Response(
        status_code=308,
        headers={"Range": f"0-{uploaded - 1}"},
    )


async def _upsert_object(
    bucket: str,
    name: str,
    data: bytes,
    content_type: str,
    metadata: dict,
    db: AsyncSession,
    base_url: str,
):
    now = datetime.now(timezone.utc)
    md5 = hashlib.md5(data).hexdigest()

    result = await db.execute(
        select(Object).where(Object.bucket_name == bucket, Object.name == name)
    )
    obj = result.scalar_one_or_none()

    if obj:
        obj.data = data
        obj.size = len(data)
        obj.content_type = content_type
        obj.md5_hash = md5
        obj.user_metadata = metadata
        obj.updated_at = now
        obj.generation += 1
    else:
        obj = Object(
            id=uuid.uuid4(),
            bucket_name=bucket,
            name=name,
            content_type=content_type,
            size=len(data),
            md5_hash=md5,
            user_metadata=metadata,
            generation=1,
            data=data,
            created_at=now,
            updated_at=now,
        )
        db.add(obj)

    await db.flush()

    class _FakeRequest:
        pass

    class _MockRequest:
        def __init__(self, base):
            self._base = base
        base_url = property(lambda self: type("B", (), {"__str__": lambda s: self._base + "/"})())

    mock_req = _MockRequest(base_url)
    return ObjectMetadataResponse.from_orm(obj, base_url).model_dump()
