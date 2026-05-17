import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.bigquery import Dataset
from gcp_simulator.app.schemas.bigquery import DatasetCreate

router = APIRouter()


def _ds_response(ds: Dataset) -> dict:
    return {
        "kind": "bigquery#dataset",
        "id": f"{ds.project_id}:{ds.dataset_id}",
        "datasetReference": {"projectId": ds.project_id, "datasetId": ds.dataset_id},
        "location": ds.location,
        "labels": ds.labels or {},
        "creationTime": str(int(ds.created_at.timestamp() * 1000)),
    }


@router.post("/bigquery/v2/projects/{project_id}/datasets")
async def create_dataset(project_id: str, body: DatasetCreate, db: AsyncSession = Depends(get_db)):
    dataset_id = body.datasetReference.get("datasetId", "")
    if not dataset_id:
        raise HTTPException(status_code=400, detail="datasetId required")

    existing = await db.execute(
        select(Dataset).where(Dataset.project_id == project_id, Dataset.dataset_id == dataset_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Dataset {dataset_id} already exists")

    ds = Dataset(
        id=uuid.uuid4(),
        project_id=project_id,
        dataset_id=dataset_id,
        location=body.location,
        labels=body.labels,
        created_at=datetime.now(timezone.utc),
    )
    db.add(ds)
    await db.flush()
    return _ds_response(ds)


@router.get("/bigquery/v2/projects/{project_id}/datasets")
async def list_datasets(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.project_id == project_id))
    datasets = result.scalars().all()
    return {"kind": "bigquery#datasetList", "datasets": [_ds_response(ds) for ds in datasets]}


@router.get("/bigquery/v2/projects/{project_id}/datasets/{dataset_id}")
async def get_dataset(project_id: str, dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Dataset).where(Dataset.project_id == project_id, Dataset.dataset_id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return _ds_response(ds)


@router.patch("/bigquery/v2/projects/{project_id}/datasets/{dataset_id}")
async def update_dataset(
    project_id: str,
    dataset_id: str,
    body: DatasetCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Dataset).where(Dataset.project_id == project_id, Dataset.dataset_id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    if body.labels:
        ds.labels = body.labels
    if body.location:
        ds.location = body.location
    await db.flush()
    return _ds_response(ds)


@router.delete("/bigquery/v2/projects/{project_id}/datasets/{dataset_id}", status_code=204)
async def delete_dataset(project_id: str, dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Dataset).where(Dataset.project_id == project_id, Dataset.dataset_id == dataset_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    await db.execute(
        delete(Dataset).where(Dataset.project_id == project_id, Dataset.dataset_id == dataset_id)
    )
