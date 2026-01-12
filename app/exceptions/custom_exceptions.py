"""
Custom exception classes for the Bank Wallet application.
All custom exceptions inherit from BankWalletException.
"""

from __future__ import annotations

from typing import Optional


class BankWalletException(Exception):
    """
    Base exception for all Bank Wallet application errors.
    Provides consistent error structure and status code.
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[list[dict]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class NotFoundException(BankWalletException):
    """Raised when a requested resource is not found."""
    
    def __init__(
        self,
        resource: str,
        identifier: Optional[str] = None,
        details: Optional[list[dict]] = None,
    ):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=details,
        )
        self.resource = resource
        self.identifier = identifier


class ValidationException(BankWalletException):
    """Raised when request validation fails."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[list[dict]] = None,
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class DatabaseException(BankWalletException):
    """Raised when database operations fail."""
    
    def __init__(
        self,
        message: str = "Database operation failed",
        details: Optional[list[dict]] = None,
    ):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details,
        )


class S3Exception(BankWalletException):
    """Raised when S3 operations fail."""
    
    def __init__(
        self,
        message: str = "S3 operation failed",
        operation: Optional[str] = None,
        details: Optional[list[dict]] = None,
    ):
        if operation:
            message = f"S3 {operation} failed: {message}"
        super().__init__(
            message=message,
            error_code="S3_ERROR",
            status_code=502,
            details=details,
        )
        self.operation = operation


class PresentationException(BankWalletException):
    """Raised when presentation definition operations fail."""
    
    def __init__(
        self,
        message: str = "Presentation operation failed",
        details: Optional[list[dict]] = None,
    ):
        super().__init__(
            message=message,
            error_code="PRESENTATION_ERROR",
            status_code=400,
            details=details,
        )


class DIDException(BankWalletException):
    """Raised when DID operations fail."""
    
    def __init__(
        self,
        message: str = "DID operation failed",
        details: Optional[list[dict]] = None,
    ):
        super().__init__(
            message=message,
            error_code="DID_ERROR",
            status_code=500,
            details=details,
        )
