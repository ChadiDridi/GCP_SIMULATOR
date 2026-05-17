from fastapi import Request, HTTPException
from gcp_simulator.app.db.engine import get_db  # noqa: F401 - re-exported for convenience


def get_project_id(request: Request) -> str:
    project_id = getattr(request.state, "project_id", None)
    if not project_id:
        raise HTTPException(status_code=401, detail="Missing project context")
    return project_id
