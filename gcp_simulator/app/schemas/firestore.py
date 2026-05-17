from pydantic import BaseModel
from typing import Any


class DocumentFields(BaseModel):
    fields: dict[str, Any] = {}


class RunQueryRequest(BaseModel):
    structuredQuery: dict | None = None
