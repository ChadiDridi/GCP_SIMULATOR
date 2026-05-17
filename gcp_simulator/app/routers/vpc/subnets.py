import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.vpc import Subnetwork

router = APIRouter()


def _subnet_response(sub: Subnetwork) -> dict:
    return {
        "kind": "compute#subnetwork",
        "id": str(sub.id),
        "name": sub.name,
        "region": sub.region,
        "network": sub.network_name,
        "ipCidrRange": sub.ip_cidr_range or "",
        "privateIpGoogleAccess": sub.private_ip_google_access,
        "secondaryIpRanges": sub.secondary_ranges or [],
        "selfLink": (
            f"https://www.googleapis.com/compute/v1/projects/{sub.project_id}"
            f"/regions/{sub.region}/subnetworks/{sub.name}"
        ),
        "creationTimestamp": sub.created_at.isoformat() if sub.created_at else None,
    }


@router.get("/compute/v1/projects/{project_id}/regions/{region}/subnetworks")
async def list_subnets(
    project_id: str,
    region: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subnetwork).where(
            Subnetwork.project_id == project_id,
            Subnetwork.region == region,
        )
    )
    subnets = result.scalars().all()
    return {
        "kind": "compute#subnetworkList",
        "items": [_subnet_response(s) for s in subnets],
    }


@router.post("/compute/v1/projects/{project_id}/regions/{region}/subnetworks", status_code=200)
async def create_subnet(
    project_id: str,
    region: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(Subnetwork).where(
            Subnetwork.project_id == project_id,
            Subnetwork.region == region,
            Subnetwork.name == name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Subnetwork {name} already exists in region {region}")

    sub = Subnetwork(
        id=uuid.uuid4(),
        project_id=project_id,
        region=region,
        network_name=body.get("network", ""),
        name=name,
        ip_cidr_range=body.get("ipCidrRange"),
        private_ip_google_access=body.get("privateIpGoogleAccess", False),
        secondary_ranges=body.get("secondaryIpRanges", []),
        created_at=datetime.now(timezone.utc),
    )
    db.add(sub)
    await db.flush()
    return _subnet_response(sub)


@router.get("/compute/v1/projects/{project_id}/regions/{region}/subnetworks/{name}")
async def get_subnet(
    project_id: str,
    region: str,
    name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subnetwork).where(
            Subnetwork.project_id == project_id,
            Subnetwork.region == region,
            Subnetwork.name == name,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Subnetwork {name} not found in region {region}")
    return _subnet_response(sub)


@router.delete(
    "/compute/v1/projects/{project_id}/regions/{region}/subnetworks/{name}",
    status_code=204,
)
async def delete_subnet(
    project_id: str,
    region: str,
    name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subnetwork).where(
            Subnetwork.project_id == project_id,
            Subnetwork.region == region,
            Subnetwork.name == name,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Subnetwork {name} not found in region {region}")
    await db.execute(
        delete(Subnetwork).where(
            Subnetwork.project_id == project_id,
            Subnetwork.region == region,
            Subnetwork.name == name,
        )
    )
