"""
api/schemas/common.py — Common API models, error wrappers, and pagination.
"""
from typing import Optional, Any
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Standardized error code string, e.g. NOT_FOUND, VALIDATION_ERROR")
    message: str = Field(description="Human-readable safe explanation of the error")
    details: Optional[Any] = Field(default=None, description="Optional safe non-sensitive error metadata")


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    has_next: bool
