from pydantic import BaseModel


class DatasetCreate(BaseModel):
    datasetReference: dict
    location: str = "US"
    labels: dict[str, str] = {}


class TableCreate(BaseModel):
    tableReference: dict
    schema_: dict | None = None
    labels: dict[str, str] = {}

    model_config = {"populate_by_name": True}

    class Config:
        fields = {"schema_": "schema"}


class InsertAllRequest(BaseModel):
    rows: list[dict]
    skipInvalidRows: bool = False
    ignoreUnknownValues: bool = False


class QueryRequest(BaseModel):
    query: str
    useLegacySql: bool = False
    location: str = "US"
