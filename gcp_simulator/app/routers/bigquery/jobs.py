import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.bigquery import Job
from gcp_simulator.app.routers.bigquery.schema_translator import pg_rows_to_bq_result
from gcp_simulator.app.schemas.bigquery import QueryRequest

router = APIRouter()


def _job_response(job: Job, project_id: str, include_results: bool = False) -> dict:
    resp = {
        "kind": "bigquery#job",
        "id": f"{project_id}:{job.job_id}",
        "jobReference": {"projectId": project_id, "jobId": job.job_id},
        "status": {
            "state": job.status,
        },
        "configuration": {
            "jobType": job.job_type,
            "query": {"query": job.query} if job.query else {},
        },
        "statistics": {
            "creationTime": str(int(job.created_at.timestamp() * 1000)),
            "startTime": str(int(job.created_at.timestamp() * 1000)),
            "endTime": str(int(job.created_at.timestamp() * 1000)),
        },
    }
    if job.error_result:
        resp["status"]["errorResult"] = job.error_result
    if include_results and job.result_rows:
        resp.update(job.result_rows)
    return resp


@router.post("/bigquery/v2/projects/{project_id}/jobs")
async def create_job(project_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    config = body.get("configuration", {})
    job_type = list(config.keys())[0].upper() if config else "QUERY"
    job_id = body.get("jobReference", {}).get("jobId") or str(uuid.uuid4())

    query = None
    result_rows = None
    error_result = None
    status = "DONE"

    if job_type == "QUERY":
        query_config = config.get("query", {})
        query = query_config.get("query", "")
        try:
            result = await db.execute(text(query))
            if result.returns_rows:
                rows = result.fetchall()
                col_names = list(result.keys())
                result_rows = pg_rows_to_bq_result(rows, col_names)
            else:
                result_rows = {"schema": {"fields": []}, "rows": [], "totalRows": "0"}
        except Exception as e:
            status = "DONE"
            error_result = {"reason": "backendError", "message": str(e), "location": "query"}

    job = Job(
        id=uuid.uuid4(),
        project_id=project_id,
        job_id=job_id,
        job_type=job_type,
        status=status,
        query=query,
        result_rows=result_rows,
        error_result=error_result,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    resp = _job_response(job, project_id)
    return resp


@router.post("/bigquery/v2/projects/{project_id}/queries")
async def run_query(
    project_id: str,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    job_id = str(uuid.uuid4())
    try:
        result = await db.execute(text(body.query))
        rows = result.fetchall() if result.returns_rows else []
        col_names = list(result.keys()) if result.returns_rows else []
        bq_result = pg_rows_to_bq_result(rows, col_names)
        error_result = None
        status = "DONE"
    except Exception as e:
        bq_result = {"schema": {"fields": []}, "rows": [], "totalRows": "0"}
        error_result = {"reason": "backendError", "message": str(e)}
        status = "DONE"

    job = Job(
        id=uuid.uuid4(),
        project_id=project_id,
        job_id=job_id,
        job_type="QUERY",
        status=status,
        query=body.query,
        result_rows=bq_result,
        error_result=error_result,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    resp = {
        "kind": "bigquery#queryResponse",
        "jobReference": {"projectId": project_id, "jobId": job_id},
        "jobComplete": True,
        "totalRows": bq_result.get("totalRows", "0"),
        "schema": bq_result.get("schema", {}),
        "rows": bq_result.get("rows", []),
    }
    if error_result:
        resp["errors"] = [error_result]
    return resp


@router.get("/bigquery/v2/projects/{project_id}/jobs/{job_id}")
async def get_job(project_id: str, job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.project_id == project_id, Job.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _job_response(job, project_id)


@router.get("/bigquery/v2/projects/{project_id}/queries/{job_id}")
async def get_query_results(project_id: str, job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.project_id == project_id, Job.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    resp = {
        "kind": "bigquery#queryResponse",
        "jobReference": {"projectId": project_id, "jobId": job_id},
        "jobComplete": True,
        "totalRows": "0",
        "schema": {"fields": []},
        "rows": [],
    }
    if job.result_rows:
        resp.update(job.result_rows)
        resp["totalRows"] = job.result_rows.get("totalRows", "0")
    return resp
