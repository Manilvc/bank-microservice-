"""
Standard error response schemas.
Provides consistent error format across all API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detail information for a single error."""
    
    field: Optional[str] = Field(
        default=None,
        description="Field name that caused the error",
    )
    message: str = Field(
        description="Human-readable error message",
    )
    code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code",
    )
    field_id: Optional[int] = Field(
        default=None,
        description="Field ID (for subject field errors)",
    )
    field_name: Optional[str] = Field(
        default=None,
        description="Field name (for subject field errors)",
    )


class ErrorResponse(BaseModel):
    """
    Standard error response format.
    All API errors return this structure.
    """
    
    success: bool = Field(
        default=False,
        description="Always false for error responses",
    )
    error: str = Field(
        description="Error type or category",
    )
    message: str = Field(
        description="Human-readable error description",
    )
    status_code: int = Field(
        description="HTTP status code",
    )
    details: Optional[list[ErrorDetail]] = Field(
        default=None,
        description="Detailed error information for validation errors",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Request tracking ID for debugging",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error occurrence timestamp",
    )
    path: Optional[str] = Field(
        default=None,
        description="Request path that caused the error",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "ValidationError",
                "message": "Request validation failed",
                "status_code": 422,
                "details": [
                    {
                        "field": "subject_id",
                        "message": "Field is required",
                        "code": "required",
                    }
                ],
                "request_id": "req_abc123",
                "timestamp": "2026-01-10T10:30:00Z",
                "path": "/api/v1/presentations",
            }
        }


class SuccessResponse(BaseModel):
    """Base success response wrapper."""
    
    success: bool = Field(
        default=True,
        description="Always true for successful responses",
    )
    message: Optional[str] = Field(
        default=None,
        description="Optional success message",
    )
    data: Optional[Any] = Field(
        default=None,
        description="Response payload",
    )
