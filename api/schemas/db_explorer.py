"""
api/schemas/db_explorer.py — Schemas for safe read-only Database Explorer.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class TableInfo(BaseModel):
    name: str
    row_count: int


class ColumnInfo(BaseModel):
    cid: int
    name: str
    data_type: str
    notnull: bool
    default_value: Optional[str] = None
    pk: bool


class ForeignKeyInfo(BaseModel):
    id: int
    seq: int
    table: str
    from_col: str
    to_col: str


class TableSchemaResponse(BaseModel):
    table_name: str
    row_count: int
    columns: List[ColumnInfo]
    foreign_keys: List[ForeignKeyInfo]


class DatabaseOverviewResponse(BaseModel):
    database_file: str
    file_size_bytes: int
    last_modified: str
    integrity_status: str
    foreign_key_violations_count: int
    total_tables: int
    tables: List[TableInfo]


class TableRowsResponse(BaseModel):
    table_name: str
    total_rows: int
    page: int
    page_size: int
    columns: List[str]
    rows: List[Dict[str, Any]]
