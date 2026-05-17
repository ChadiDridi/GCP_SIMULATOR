import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.dataform import Repository, Workspace

router = APIRouter()


def _ws_response(ws: Workspace) -> dict:
    return {
        "name": str(ws.id),
        "id": str(ws.id),
        "repositoryId": str(ws.repository_id),
        "workspaceName": ws.name,
        "createTime": ws.created_at.isoformat() if ws.created_at else None,
    }


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


async def _get_ws_or_404(
    repo_id: uuid.UUID, ws_name: str, db: AsyncSession
) -> Workspace:
    result = await db.execute(
        select(Workspace).where(
            Workspace.repository_id == repo_id,
            Workspace.name == ws_name,
        )
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace {ws_name} not found")
    return ws


@router.get(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}/workspaces"
)
async def list_workspaces(
    project_id: str,
    location: str,
    repo_name: str,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo_or_404(project_id, location, repo_name, db)
    result = await db.execute(
        select(Workspace).where(Workspace.repository_id == repo.id)
    )
    workspaces = result.scalars().all()
    return {"workspaces": [_ws_response(w) for w in workspaces]}


@router.post(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}/workspaces",
    status_code=200,
)
async def create_workspace(
    project_id: str,
    location: str,
    repo_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo_or_404(project_id, location, repo_name, db)
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(Workspace).where(
            Workspace.repository_id == repo.id, Workspace.name == name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Workspace {name} already exists")

    ws = Workspace(
        id=uuid.uuid4(),
        repository_id=repo.id,
        name=name,
        files={},
        created_at=datetime.now(timezone.utc),
    )
    db.add(ws)
    await db.flush()
    return _ws_response(ws)


@router.get(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}/workspaces/{ws_name}"
)
async def get_workspace(
    project_id: str,
    location: str,
    repo_name: str,
    ws_name: str,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo_or_404(project_id, location, repo_name, db)
    ws = await _get_ws_or_404(repo.id, ws_name, db)
    return _ws_response(ws)


@router.delete(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}/workspaces/{ws_name}",
    status_code=204,
)
async def delete_workspace(
    project_id: str,
    location: str,
    repo_name: str,
    ws_name: str,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo_or_404(project_id, location, repo_name, db)
    ws = await _get_ws_or_404(repo.id, ws_name, db)
    await db.execute(
        delete(Workspace).where(
            Workspace.repository_id == repo.id, Workspace.name == ws_name
        )
    )


@router.post(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}/workspaces/{ws_name}:writeFile"
)
async def write_file(
    project_id: str,
    location: str,
    repo_name: str,
    ws_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo_or_404(project_id, location, repo_name, db)
    ws = await _get_ws_or_404(repo.id, ws_name, db)
    body = await request.json()
    path = body.get("path")
    contents = body.get("contents")  # base64-encoded string
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    files = dict(ws.files or {})
    files[path] = contents
    ws.files = files
    await db.flush()
    return {"path": path}


@router.post(
    "/v1beta1/projects/{project_id}/locations/{location}/repositories/{repo_name}/workspaces/{ws_name}:readFile"
)
async def read_file(
    project_id: str,
    location: str,
    repo_name: str,
    ws_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo_or_404(project_id, location, repo_name, db)
    ws = await _get_ws_or_404(repo.id, ws_name, db)
    body = await request.json()
    path = body.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    files = ws.files or {}
    if path not in files:
        raise HTTPException(status_code=404, detail=f"File {path} not found in workspace")
    return {"contents": files[path], "path": path}
