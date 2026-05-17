import base64
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.bigtable import BigtableRow

router = APIRouter()


def _decode_row_key(raw: str) -> str:
    """Decode a base64-encoded row key to a UTF-8 string for storage."""
    try:
        return base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return raw


def _encode_row_key(key: str) -> str:
    return base64.b64encode(key.encode()).decode()


@router.post(
    "/v2/projects/{project_id}/instances/{instance_id}/tables/{table_id}/mutateRows"
)
async def mutate_rows(
    project_id: str, instance_id: str, table_id: str, body: dict, db: AsyncSession = Depends(get_db)
):
    entries = body.get("entries", [])
    now = datetime.now(timezone.utc)

    for entry in entries:
        raw_key = entry.get("rowKey", "")
        row_key = _decode_row_key(raw_key)
        mutations = entry.get("mutations", [])

        # Fetch or create row
        result = await db.execute(
            select(BigtableRow).where(
                BigtableRow.project_id == project_id,
                BigtableRow.instance_id == instance_id,
                BigtableRow.table_id == table_id,
                BigtableRow.row_key == row_key,
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = BigtableRow(
                id=uuid.uuid4(),
                project_id=project_id,
                instance_id=instance_id,
                table_id=table_id,
                row_key=row_key,
                cells={},
                created_at=now,
                updated_at=now,
            )
            db.add(row)

        cells = dict(row.cells or {})

        delete_row = False
        for mutation in mutations:
            if "setCell" in mutation:
                sc = mutation["setCell"]
                family = sc.get("familyName", "")
                qualifier = sc.get("columnQualifier", "")
                try:
                    qualifier_str = base64.b64decode(qualifier).decode("utf-8", errors="replace")
                except Exception:
                    qualifier_str = qualifier
                value = sc.get("value", "")
                ts = sc.get("timestampMicros", int(now.timestamp() * 1_000_000))

                if family not in cells:
                    cells[family] = {}
                if qualifier_str not in cells[family]:
                    cells[family][qualifier_str] = []
                cells[family][qualifier_str].append({"value": value, "timestamp_micros": ts})

            elif "deleteFromColumn" in mutation:
                dfc = mutation["deleteFromColumn"]
                family = dfc.get("familyName", "")
                qualifier = dfc.get("columnQualifier", "")
                try:
                    qualifier_str = base64.b64decode(qualifier).decode("utf-8", errors="replace")
                except Exception:
                    qualifier_str = qualifier
                if family in cells and qualifier_str in cells[family]:
                    del cells[family][qualifier_str]

            elif "deleteFromRow" in mutation:
                delete_row = True
                break

        if delete_row:
            await db.delete(row)
        else:
            row.cells = cells
            row.updated_at = now

    await db.flush()
    return {"entries": [{"index": str(i), "status": {}} for i in range(len(entries))]}


@router.post(
    "/v2/projects/{project_id}/instances/{instance_id}/tables/{table_id}/readRows"
)
async def read_rows(
    project_id: str, instance_id: str, table_id: str, body: dict, db: AsyncSession = Depends(get_db)
):
    rows_filter = body.get("rows", {})
    row_keys = rows_filter.get("rowKeys", [])
    row_ranges = rows_filter.get("rowRanges", [])

    query = select(BigtableRow).where(
        BigtableRow.project_id == project_id,
        BigtableRow.instance_id == instance_id,
        BigtableRow.table_id == table_id,
    )

    if row_keys:
        decoded_keys = [_decode_row_key(k) for k in row_keys]
        query = query.where(BigtableRow.row_key.in_(decoded_keys))

    result = await db.execute(query)
    rows = result.scalars().all()

    chunks = []
    for row in rows:
        encoded_key = _encode_row_key(row.row_key)
        chunks.append({
            "rowKey": encoded_key,
            "familyName": None,
            "qualifier": None,
            "timestampMicros": None,
            "value": None,
            "labels": [],
            "commitRow": True,
            "cells": row.cells or {},
        })

    return {"chunks": chunks}


@router.post(
    "/v2/projects/{project_id}/instances/{instance_id}/tables/{table_id}/sampleRowKeys"
)
async def sample_row_keys(
    project_id: str, instance_id: str, table_id: str, db: AsyncSession = Depends(get_db)
):
    return [{"rowKey": "", "offsetBytes": "0"}]
