import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.firestore import Document
from gcp_simulator.app.schemas.firestore import DocumentFields, RunQueryRequest

router = APIRouter()

_FS_BASE = "/v1/projects/{project_id}/databases/{database_id}/documents"


def _doc_name(project_id: str, database_id: str, collection_id: str, document_id: str) -> str:
    return f"projects/{project_id}/databases/{database_id}/documents/{collection_id}/{document_id}"


def _doc_response(doc: Document) -> dict:
    return {
        "name": _doc_name(doc.project_id, doc.database_id, doc.collection_id, doc.document_id),
        "fields": doc.fields or {},
        "createTime": doc.create_time.isoformat() + "Z",
        "updateTime": doc.update_time.isoformat() + "Z",
    }


@router.post("/v1/projects/{project_id}/databases/{database_id}/documents/{collection_id}")
async def create_document(
    project_id: str,
    database_id: str,
    collection_id: str,
    body: DocumentFields,
    db: AsyncSession = Depends(get_db),
):
    document_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc = Document(
        id=uuid.uuid4(),
        project_id=project_id,
        database_id=database_id,
        collection_id=collection_id,
        document_id=document_id,
        fields=body.fields,
        create_time=now,
        update_time=now,
    )
    db.add(doc)
    await db.flush()
    return _doc_response(doc)


@router.get("/v1/projects/{project_id}/databases/{database_id}/documents/{collection_id}/{document_id}")
async def get_document(
    project_id: str,
    database_id: str,
    collection_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.database_id == database_id,
            Document.collection_id == collection_id,
            Document.document_id == document_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_response(doc)


@router.patch("/v1/projects/{project_id}/databases/{database_id}/documents/{collection_id}/{document_id}")
async def upsert_document(
    project_id: str,
    database_id: str,
    collection_id: str,
    document_id: str,
    body: DocumentFields,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.database_id == database_id,
            Document.collection_id == collection_id,
            Document.document_id == document_id,
        )
    )
    doc = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if doc:
        doc.fields = body.fields
        doc.update_time = now
    else:
        doc = Document(
            id=uuid.uuid4(),
            project_id=project_id,
            database_id=database_id,
            collection_id=collection_id,
            document_id=document_id,
            fields=body.fields,
            create_time=now,
            update_time=now,
        )
        db.add(doc)

    await db.flush()
    return _doc_response(doc)


@router.delete(
    "/v1/projects/{project_id}/databases/{database_id}/documents/{collection_id}/{document_id}",
    status_code=200,
)
async def delete_document(
    project_id: str,
    database_id: str,
    collection_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.database_id == database_id,
            Document.collection_id == collection_id,
            Document.document_id == document_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")
    await db.execute(
        delete(Document).where(
            Document.project_id == project_id,
            Document.database_id == database_id,
            Document.collection_id == collection_id,
            Document.document_id == document_id,
        )
    )
    return {}


@router.get("/v1/projects/{project_id}/databases/{database_id}/documents/{collection_id}")
async def list_documents(
    project_id: str,
    database_id: str,
    collection_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.database_id == database_id,
            Document.collection_id == collection_id,
        )
    )
    docs = result.scalars().all()
    return {"documents": [_doc_response(d) for d in docs]}


@router.post("/v1/projects/{project_id}/databases/{database_id}/documents:runQuery")
async def run_query(
    project_id: str,
    database_id: str,
    body: RunQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    if not body.structuredQuery:
        raise HTTPException(status_code=400, detail="structuredQuery required")

    sq = body.structuredQuery
    from_clauses = sq.get("from", [])
    collection_id = from_clauses[0].get("collectionId") if from_clauses else None

    query = select(Document).where(
        Document.project_id == project_id,
        Document.database_id == database_id,
    )

    if collection_id:
        query = query.where(Document.collection_id == collection_id)

    where_clause = sq.get("where")
    if where_clause:
        query = _apply_where(query, where_clause)

    limit = sq.get("limit")
    if limit:
        query = query.limit(int(limit))

    result = await db.execute(query)
    docs = result.scalars().all()
    return [{"document": _doc_response(d)} for d in docs]


def _apply_where(query, where_clause):
    """Translate Firestore StructuredQuery where to SQLAlchemy filter."""
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import JSONB

    filter_type = list(where_clause.keys())[0] if where_clause else None

    if filter_type == "fieldFilter":
        ff = where_clause["fieldFilter"]
        field_path = ff["field"]["fieldPath"]
        op = ff["op"]
        value = _extract_value(ff["value"])

        # Access JSONB field
        field_expr = Document.fields[field_path].astext

        if op == "EQUAL":
            return query.where(field_expr == str(value) if value is not None else field_expr.is_(None))
        elif op == "NOT_EQUAL":
            return query.where(field_expr != str(value))
        elif op == "LESS_THAN":
            return query.where(field_expr < str(value))
        elif op == "LESS_THAN_OR_EQUAL":
            return query.where(field_expr <= str(value))
        elif op == "GREATER_THAN":
            return query.where(field_expr > str(value))
        elif op == "GREATER_THAN_OR_EQUAL":
            return query.where(field_expr >= str(value))

    elif filter_type == "compositeFilter":
        cf = where_clause["compositeFilter"]
        op = cf.get("op", "AND")
        for f in cf.get("filters", []):
            query = _apply_where(query, f)

    return query


def _extract_value(value_dict: dict) -> Any:
    """Extract Python value from Firestore typed value dict."""
    if "stringValue" in value_dict:
        return value_dict["stringValue"]
    if "integerValue" in value_dict:
        return int(value_dict["integerValue"])
    if "doubleValue" in value_dict:
        return float(value_dict["doubleValue"])
    if "booleanValue" in value_dict:
        return value_dict["booleanValue"]
    if "nullValue" in value_dict:
        return None
    if "timestampValue" in value_dict:
        return value_dict["timestampValue"]
    return str(value_dict)
