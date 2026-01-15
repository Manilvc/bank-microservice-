"""
Subject and SubjectField Pydantic schemas.
Used for API request validation and response serialization.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SubjectFieldResponse(BaseModel):
    """Schema for subject field in API responses."""
    
    id: int = Field(description="Field unique identifier")
    field_key: str = Field(description="Machine-readable field key")
    field_name: str = Field(description="Human-readable field name")
    field_description: str = Field(description="Field description")
    field_type: str = Field(description="Data type (string, date, number)")
    is_required: bool = Field(description="Whether field is mandatory")
    display_order: int = Field(description="Order for UI display")
    
    class Config:
        from_attributes = True


class SubjectResponse(BaseModel):
    """Schema for subject in list responses."""
    
    id: int = Field(description="Subject unique identifier")
    name: str = Field(description="Subject name (e.g., Aadhar Card)")
    description: str = Field(description="Subject description")
    icon_name: str = Field(description="Icon identifier for UI")
    icon_color: str = Field(description="Icon color hex code")
    did: str = Field(description="Decentralized Identifier for this subject")
    field_count: int = Field(description="Number of available fields")
    is_active: bool = Field(description="Whether subject is available")
    
    class Config:
        from_attributes = True


class SubjectDetailResponse(BaseModel):
    """Schema for subject with fields in detail responses."""
    
    id: int = Field(description="Subject unique identifier")
    name: str = Field(description="Subject name")
    description: str = Field(description="Subject description")
    icon_name: str = Field(description="Icon identifier")
    icon_color: str = Field(description="Icon color hex code")
    did: str = Field(description="Decentralized Identifier")
    is_active: bool = Field(description="Whether subject is active")
    fields: list[SubjectFieldResponse] = Field(description="Available fields")
    created_at: datetime = Field(description="Creation timestamp")
    
    class Config:
        from_attributes = True


class SubjectListResponse(BaseModel):
    """Wrapper for subject list API response."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Subjects retrieved successfully")
    data: list[SubjectResponse] = Field(description="List of subjects")
    total: int = Field(description="Total count of subjects")


class SubjectFieldListResponse(BaseModel):
    """Wrapper for subject fields API response."""
    
    success: bool = Field(default=True)
    message: str = Field(default="Subject fields retrieved successfully")
    data: SubjectDetailResponse = Field(description="Subject with fields")


class CreateSubjectRequest(BaseModel):
    """Schema for creating a new subject."""
    
    name: str = Field(
        min_length=2,
        max_length=100,
        description="Subject name",
    )
    description: str = Field(
        min_length=10,
        max_length=500,
        description="Subject description",
    )
    icon_name: str = Field(
        max_length=50,
        description="Icon identifier",
    )
    icon_color: str = Field(
        default="#ffffff",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Icon color in hex format",
    )


class CreateSubjectFieldRequest(BaseModel):
    """Schema for creating a subject field."""
    
    field_key: str = Field(
        min_length=2,
        max_length=50,
        description="Machine-readable key",
    )
    field_name: str = Field(
        min_length=2,
        max_length=100,
        description="Human-readable name",
    )
    field_description: str = Field(
        min_length=5,
        max_length=255,
        description="Field description",
    )
    field_type: str = Field(
        default="string",
        pattern=r"^(string|date|number|boolean|image)$",
        description="Field data type",
    )
    is_required: bool = Field(
        default=False,
        description="Whether field is mandatory",
    )
    display_order: int = Field(
        default=0,
        ge=0,
        description="Display order",
    )
