import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.dataform import Repository, CompilationResult

router = APIRouter()


def _repo_response(repo: Repository) -> dict:
    return {
        "name": (
            f"projects/{repo.project_id}/locations/{repo.location}/repositories/{repo.name}"
        ),
        "gitRemoteSettings": repo.git_remote_settings or {},
        "createTime": repo.created_at.isoformat() if repo.created_at else None,
    }


def _compilation_response(cr: CompilationResult) -> dict:
    return {
        "name": cr.result_id,
        "gitCommitish": cr.git_commitish or "",
        "codeCompilationConfig": cr.code_compilation_config or {},
        "compilationErrors": cr.compilation_errors or [],
        "compiledAt": cr.compiled_at.isoformat() if cr.compiled_at else None,
    }


@router.get("/v1beta1/projects/{project_id}/locations/{location}/repositories")
async def list_repositories(
    project_id: str,
    location: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Repository).where(
            Repository.project_id == project_id, Repository.location == location
        )
    )
    repos = result.scalars().all()
    return {"repositories": [_repo_response(r) for r in repos]}


@router.post("/v1beta1/projects/{project_id}/locations/{location}/repositories", status_code=200)
async def create_repository(
    project_id: str,
    location: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(Repository).where(
            Repository.project_id == project_id,
            Repository.location == location,
            Repository.name == name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Repository {name} already exists")

    repo = Repository(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        name=name,
        git_remote_settings=body.get("gitRemoteSettings", {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(repo)
    await db.flush()
    return _repo_response(repo)


@router.get("/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}")
async def get_repository(
    project_id: str,
    location: str,
    repo_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Repository).where(
            Repository.project_id == project_id,
            Repository.location == location,
            Repository.name == repo_name,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository {repo_name} not found")
    return _repo_response(repo)


@router.delete(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}",
    status_code=204,
)
async def delete_repository(
    project_id: str,
    location: str,
    repo_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Repository).where(
            Repository.project_id == project_id,
            Repository.location == location,
            Repository.name == repo_name,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository {repo_name} not found")
    await db.execute(
        delete(Repository).where(
            Repository.project_id == project_id,
            Repository.location == location,
            Repository.name == repo_name,
        )
    )


# ---- Compilation Results ----


async def _get_repo_or_404(
    project_id: str, location: str, repo_name: str, db: AsyncSession
) -> Repository:
    result = await db.execute(
        select(Repository).where(
            Repository.project_id == project_id,
            Repository.location == location,
            Repository.name == repo_name,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository {repo_name} not found")
    return repo


@router.post(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}/compilationResults"
)
async def create_compilation_result(
    project_id: str,
    location: str,
    repo_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo_or_404(project_id, location, repo_name, db)
    body = await request.json()
    now = datetime.now(timezone.utc)
    result_id = str(uuid.uuid4())

    cr = CompilationResult(
        id=uuid.uuid4(),
        repository_id=repo.id,
        result_id=result_id,
        git_commitish=body.get("gitCommitish"),
        code_compilation_config=body.get("codeCompilationConfig", {}),
        compiled_at=now,
        compilation_errors=[],
    )
    db.add(cr)
    await db.flush()
    return _compilation_response(cr)


@router.get(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}/compilationResults/{result_id}"
)
async def get_compilation_result(
    project_id: str,
    location: str,
    repo_name: str,
    result_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo_or_404(project_id, location, repo_name, db)
    result = await db.execute(
        select(CompilationResult).where(
            CompilationResult.repository_id == repo.id,
            CompilationResult.result_id == result_id,
        )
    )
    cr = result.scalar_one_or_none()
    if not cr:
        raise HTTPException(status_code=404, detail=f"CompilationResult {result_id} not found")
    return _compilation_response(cr)


@router.get(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}/compilationResults/{result_id}:query"
)
async def query_compilation_result(
    project_id: str,
    location: str,
    repo_name: str,
    result_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo_or_404(project_id, location, repo_name, db)
    result = await db.execute(
        select(CompilationResult).where(
            CompilationResult.repository_id == repo.id,
            CompilationResult.result_id == result_id,
        )
    )
    cr = result.scalar_one_or_none()
    if not cr:
        raise HTTPException(status_code=404, detail=f"CompilationResult {result_id} not found")
    return {"compilationResultActions": []}
