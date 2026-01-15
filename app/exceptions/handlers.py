"""
Global exception handlers for FastAPI application.
Converts exceptions to standard error response format.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions.custom_exceptions import BankWalletException
from app.schemas.error import ErrorResponse, ErrorDetail

logger = logging.getLogger(__name__)


def create_error_response(
    error: str,
    message: str,
    status_code: int,
    request: Request,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    """
    Create standardized error response.
    Adds request ID and path for debugging.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:12])
    
    error_response = ErrorResponse(
        success=False,
        error=error,
        message=message,
        status_code=status_code,
        details=details,
        request_id=request_id,
        timestamp=datetime.utcnow(),
        path=str(request.url.path),
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(mode="json"),
    )


async def bank_wallet_exception_handler(
    request: Request,
    exc: BankWalletException,
) -> JSONResponse:
    """Handle custom BankWalletException and subclasses."""
    
    logger.warning(
        f"BankWalletException: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )
    
    details = None
    if exc.details:
        details = [
            ErrorDetail(
                field=d.get("field"),
                message=d.get("message", "Unknown error"),
                code=d.get("code"),
                field_id=d.get("field_id"),
                field_name=d.get("field_name"),
            )
            for d in exc.details
        ]
    
    return create_error_response(
        error=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        request=request,
        details=details,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle Pydantic/FastAPI validation errors."""
    
    details = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []))
        details.append(
            ErrorDetail(
                field=field,
                message=error.get("msg", "Validation error"),
                code=error.get("type", "validation_error"),
            )
        )
    
    logger.warning(
        f"Validation error: {len(details)} field(s)",
        extra={"path": request.url.path, "errors": exc.errors()},
    )
    
    return create_error_response(
        error="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=422,
        request=request,
        details=details,
    )


async def pydantic_validation_handler(
    request: Request,
    exc: ValidationError,
) -> JSONResponse:
    """Handle direct Pydantic ValidationError."""
    
    details = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []))
        details.append(
            ErrorDetail(
                field=field,
                message=error.get("msg", "Validation error"),
                code=error.get("type", "validation_error"),
            )
        )
    
    return create_error_response(
        error="VALIDATION_ERROR",
        message="Data validation failed",
        status_code=422,
        request=request,
        details=details,
    )


async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    """Handle SQLAlchemy database errors."""
    
    logger.error(
        f"Database error: {str(exc)}",
        extra={"path": request.url.path},
        exc_info=True,
    )
    
    return create_error_response(
        error="DATABASE_ERROR",
        message="A database error occurred. Please try again later.",
        status_code=500,
        request=request,
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle unexpected exceptions."""
    
    logger.error(
        f"Unexpected error: {type(exc).__name__}: {str(exc)}",
        extra={"path": request.url.path},
        exc_info=True,
    )
    
    return create_error_response(
        error="INTERNAL_ERROR",
        message="An unexpected error occurred. Please try again later.",
        status_code=500,
        request=request,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI app.
    Order matters: more specific handlers first.
    """
    app.add_exception_handler(BankWalletException, bank_wallet_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
