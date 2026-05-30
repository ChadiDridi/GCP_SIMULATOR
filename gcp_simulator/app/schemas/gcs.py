from datetime import datetime
from typing import Any
from pydantic import BaseModel


class BucketCreate(BaseModel):
    name: str
    location: str = "US"
    storageClass: str = "STANDARD"
    labels: dict[str, str] = {}


class BucketResponse(BaseModel):
    kind: str = "storage#bucket"
    id: str
    name: str
    projectNumber: str
    location: str
    storageClass: str
    versioning: dict | None = None
    labels: dict[str, str] = {}
    timeCreated: str
    selfLink: str

    @classmethod
    def from_orm(cls, b, base_url: str = "http://localhost:9099") -> "BucketResponse":
        return cls(
            id=b.name,
            name=b.name,
            projectNumber="123456789",
            location=b.location,
            storageClass=b.storage_class,
            versioning={"enabled": True} if b.versioning else None,
            labels=b.labels or {},
            timeCreated=b.created_at.isoformat() + "Z",
            selfLink=f"{base_url}/storage/v1/b/{b.name}",
        )


class ObjectMetadataResponse(BaseModel):
    kind: str = "storage#object"
    id: str
    name: str
    bucket: str
    contentType: str
    size: str
    md5Hash: str | None = None
    crc32c: str | None = None
    generation: str
    metadata: dict[str, str] = {}
    timeCreated: str
    updated: str
    selfLink: str
    mediaLink: str

    @classmethod
    def from_orm(cls, obj, base_url: str = "http://localhost:9099") -> "ObjectMetadataResponse":
        return cls(
            id=f"{obj.bucket_name}/{obj.name}",
            name=obj.name,
            bucket=obj.bucket_name,
            contentType=obj.content_type or "application/octet-stream",
            size=str(obj.size or 0),
            md5Hash=obj.md5_hash,
            crc32c=obj.crc32c,
            generation=str(obj.generation),
            metadata=obj.user_metadata or {},
            timeCreated=obj.created_at.isoformat() + "Z",
            updated=obj.updated_at.isoformat() + "Z",
            selfLink=f"{base_url}/storage/v1/b/{obj.bucket_name}/o/{obj.name}",
            mediaLink=f"{base_url}/download/storage/v1/b/{obj.bucket_name}/o/{obj.name}?alt=media",
        )
