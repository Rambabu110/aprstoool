"""
api/routers/db_explorer.py — Read-only Database Explorer endpoints.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from api.schemas.db_explorer import (
    DatabaseOverviewResponse,
    TableSchemaResponse,
    TableRowsResponse
)
from api.services.db_explorer_service import DbExplorerService

router = APIRouter(prefix="/db-explorer", tags=["database-explorer"])


@router.get("/overview", response_model=DatabaseOverviewResponse)
def get_database_overview():
    """Returns database metadata, integrity check, and all table row counts."""
    return DbExplorerService.get_overview()


@router.get("/schema/{table_name}", response_model=TableSchemaResponse)
def get_table_schema(table_name: str):
    """Returns column schema and foreign keys for an allowlisted table."""
    res = DbExplorerService.get_table_schema(table_name)
    if not res:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist or is not accessible.")
    return res


@router.get("/rows/{table_name}", response_model=TableRowsResponse)
def get_table_rows(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    """Returns paginated, searchable rows for an allowlisted table."""
    res = DbExplorerService.get_table_rows(
        table_name=table_name,
        page=page,
        page_size=page_size,
        search=search
    )
    if not res:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist or is not accessible.")
    return res
