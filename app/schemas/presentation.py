"""
Presentation Definition Pydantic schemas.
Based on DIF Presentation Exchange specification.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RequestedFieldInfo(BaseModel):
    """Information about a requested field."""
    
    field_id: int = Field(description="Field ID from subject")
    field_key: str = Field(description="Field key identifier")
    field_name: str = Field(description="Human-readable field name")
    is_required: bool = Field(description="Whether field is mandatory")


class CreatePresentationRequest(BaseModel):
    """Request schema for creating a presentation definition."""
    
    subject_id: int = Field(
        gt=0,
        description="Subject ID to create presentation for",
    )
    account_type: str = Field(
        min_length=2,
        max_length=50,
        description="Account type (e.g., Savings Account)",
    )
    field_ids: list[int] = Field(
        min_length=1,
        description="List of field IDs to request",
    )
    purpose: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Purpose of the verification request",
    )
    expiry_hours: Optional[int] = Field(
        default=None,
        ge=1,
        le=168,
        description="Hours until expiration (default: 24)",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "subject_id": 1,
                "account_type": "Savings Account",
                "field_ids": [1, 2, 5],
                "purpose": "KYC verification for account opening",
                "expiry_hours": 24,
            }
        }


class PresentationSummaryResponse(BaseModel):
    """Summary of created presentation definition."""
    
    definition_id: str = Field(description="Unique presentation definition ID")
    account_type: str = Field(description="Account type")
    document_name: str = Field(description="Subject/document name")
    created_at: datetime = Field(description="Creation timestamp")
    expires_at: datetime = Field(description="Expiration timestamp")
    requested_fields: list[RequestedFieldInfo] = Field(description="Requested fields")
    qr_code_url: str = Field(description="URL to QR code image")
    status: str = Field(description="Presentation status")


class PresentationDefinitionResponse(BaseModel):
    """Full response for created presentation definition."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Presentation definition created successfully")
    data: PresentationSummaryResponse = Field(description="Presentation summary")


class PresentationListResponse(BaseModel):
    """Response for listing presentation definitions."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Presentations retrieved successfully")
    data: list[PresentationSummaryResponse] = Field(description="List of presentations")
    total: int = Field(description="Total count")


class DIFInputDescriptor(BaseModel):
    """DIF Input Descriptor schema."""
    
    id: str = Field(description="Descriptor ID")
    name: str = Field(description="Descriptor name")
    purpose: str = Field(description="Purpose of this input")
    constraints: dict = Field(description="Field constraints")


class DIFPresentationDefinition(BaseModel):
    """
    DIF Presentation Definition format.
    Conforms to Presentation Exchange specification.
    """
    
    id: str = Field(description="Presentation definition ID")
    name: str = Field(description="Presentation name")
    purpose: str = Field(description="Overall purpose")
    input_descriptors: list[DIFInputDescriptor] = Field(
        description="List of input descriptors"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "1768025257083-r6tb41323",
                "name": "Aadhar Card Verification",
                "purpose": "KYC verification for Savings Account",
                "input_descriptors": [
                    {
                        "id": "full_name",
                        "name": "Full Name",
                        "purpose": "Verify holder identity",
                        "constraints": {
                            "fields": [
                                {
                                    "path": ["$.credentialSubject.fullName"],
                                    "purpose": "Complete name as per Aadhar",
                                }
                            ]
                        },
                    }
                ],
            }
        }


# Submission Schemas
class SubmitPresentationRequest(BaseModel):
    """Request schema for submitting a presentation."""
    
    holder_did: Optional[str] = Field(
        default=None,
        description="Holder's DID (Decentralized Identifier)",
    )
    submission_json: dict = Field(
        description="Submitted credential data matching the presentation definition"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "holder_did": "did:evrc:holder123",
                "submission_json": {
                    "credentialSubject": {
                        "name": "John Doe",
                        "date_of_birth": "1990-01-01",
                        "address": "123 Main St",
                    }
                },
            }
        }


class SubmissionResponse(BaseModel):
    """Response schema for a submission."""
    
    request_id: str = Field(description="Unique submission request ID")
    definition_id: str = Field(description="Presentation definition ID")
    account_type: str = Field(description="Account type")
    document_name: str = Field(description="Document/subject name")
    holder_did: Optional[str] = Field(description="Holder's DID")
    status: str = Field(description="Submission status (pending, approved, rejected)")
    created_at: datetime = Field(description="Submission timestamp")
    completed_at: Optional[datetime] = Field(description="Completion timestamp")
    submission_json: Optional[dict] = Field(description="Submitted data")


class SubmissionListResponse(BaseModel):
    """Response for listing submissions."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Submissions retrieved successfully")
    data: list[SubmissionResponse] = Field(description="List of submissions")
    total: int = Field(description="Total count")


class UpdateSubmissionStatusRequest(BaseModel):
    """Request schema for updating submission status."""
    
    status: str = Field(
        description="New status (approved, rejected)",
        pattern="^(approved|rejected)$",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "approved",
            }
        }


# Dashboard Schemas
class DashboardStatisticsResponse(BaseModel):
    """Response schema for dashboard statistics."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Statistics retrieved successfully")
    data: dict = Field(
        description="Statistics data",
        json_schema_extra={
            "example": {
                "pending_reviews": 3,
                "approved": 1,
                "rejected": 1,
                "qr_definitions": 4,
                "pending_today": 2,
                "approved_this_week": 5,
            }
        },
    )


class RecentActivityResponse(BaseModel):
    """Response schema for recent activity."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Recent activity retrieved successfully")
    data: list[SubmissionResponse] = Field(description="List of recent submissions")


# Submission Schemas
class SubmitPresentationRequest(BaseModel):
    """Request schema for submitting a presentation."""
    
    holder_did: Optional[str] = Field(
        default=None,
        description="Holder's DID (Decentralized Identifier)",
    )
    submission_json: dict = Field(
        description="Submitted credential data matching the presentation definition"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "holder_did": "did:evrc:holder123",
                "submission_json": {
                    "credentialSubject": {
                        "name": "John Doe",
                        "date_of_birth": "1990-01-01",
                        "address": "123 Main St",
                    }
                },
            }
        }


class SubmissionResponse(BaseModel):
    """Response schema for a submission."""
    
    request_id: str = Field(description="Unique submission request ID")
    definition_id: str = Field(description="Presentation definition ID")
    account_type: str = Field(description="Account type")
    document_name: str = Field(description="Document/subject name")
    holder_did: Optional[str] = Field(description="Holder's DID")
    status: str = Field(description="Submission status (pending, approved, rejected)")
    created_at: datetime = Field(description="Submission timestamp")
    completed_at: Optional[datetime] = Field(description="Completion timestamp")
    submission_json: Optional[dict] = Field(description="Submitted data")


class SubmissionListResponse(BaseModel):
    """Response for listing submissions."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Submissions retrieved successfully")
    data: list[SubmissionResponse] = Field(description="List of submissions")
    total: int = Field(description="Total count")


class UpdateSubmissionStatusRequest(BaseModel):
    """Request schema for updating submission status."""
    
    status: str = Field(
        description="New status (approved, rejected)",
        pattern="^(approved|rejected)$",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "approved",
            }
        }


# Dashboard Schemas
class DashboardStatisticsResponse(BaseModel):
    """Response schema for dashboard statistics."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Statistics retrieved successfully")
    data: dict = Field(
        description="Statistics data",
        json_schema_extra={
            "example": {
                "pending_reviews": 3,
                "approved": 1,
                "rejected": 1,
                "qr_definitions": 4,
                "pending_today": 2,
                "approved_this_week": 5,
            }
        },
    )


class RecentActivityResponse(BaseModel):
    """Response schema for recent activity."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Recent activity retrieved successfully")
    data: list[SubmissionResponse] = Field(description="List of recent submissions")
