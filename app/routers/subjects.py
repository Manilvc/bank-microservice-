"""
Subject API endpoints.
Manages KYC document types and their fields.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.subject_service import SubjectService
from app.services.auth_service import get_current_user
from app.schemas.auth import UserContext
from app.schemas.subject import (
    SubjectResponse,
    SubjectListResponse,
    SubjectDetailResponse,
    SubjectFieldListResponse,
    SubjectFieldResponse,
    CreateSubjectRequest,
    CreateSubjectFieldRequest,
)
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/subjects", tags=["Subjects"])


def get_subject_service(db: Session = Depends(get_db)) -> SubjectService:
    """Dependency for SubjectService."""
    return SubjectService(db=db)


@router.get(
    "",
    response_model=SubjectListResponse,
    summary="List Subjects",
    description="Get all available KYC document types",
    responses={
        200: {"description": "Subjects retrieved successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def list_subjects(
    active_only: bool = True,
    user: UserContext = Depends(get_current_user),
    service: SubjectService = Depends(get_subject_service),
) -> SubjectListResponse:
    """
    List all subjects (KYC document types) for the authenticated user's use case.
    
    Returns subjects like Aadhar Card, PAN Card, Voter ID
    with their descriptions, icons, and field counts.
    """
    subjects = service.get_all_subjects(
        use_case=user.use_case,
        active_only=active_only,
    )
    
    subject_responses = [
        SubjectResponse(
            id=s.id,
            name=s.name,
            description=s.description,
            icon_name=s.icon_name,
            icon_color=s.icon_color,
            did=s.did,
            field_count=s.field_count,
            is_active=s.is_active,
        )
        for s in subjects
    ]
    
    return SubjectListResponse(
        success=True,
        message="Subjects retrieved successfully",
        data=subject_responses,
        total=len(subject_responses),
    )


@router.get(
    "/{subject_id}",
    response_model=SubjectFieldListResponse,
    summary="Get Subject with Fields",
    description="Get a subject with all its extractable fields",
    responses={
        200: {"description": "Subject retrieved successfully"},
        404: {"model": ErrorResponse, "description": "Subject not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_subject_fields(
    subject_id: int,
    user: UserContext = Depends(get_current_user),
    service: SubjectService = Depends(get_subject_service),
) -> SubjectFieldListResponse:
    """
    Get subject details with all available fields.
    
    Returns the subject information along with all
    extractable fields (Full Name, DOB, Address, etc.)
    Validates subject belongs to user's use case.
    """
    subject = service.get_subject_by_id(
        subject_id=subject_id,
        use_case=user.use_case,
    )
    subject = service.get_subject_with_fields(subject_id=subject_id)
    
    field_responses = [
        SubjectFieldResponse(
            id=f.id,
            field_key=f.field_key,
            field_name=f.field_name,
            field_description=f.field_description,
            field_type=f.field_type,
            is_required=f.is_required,
            display_order=f.display_order,
        )
        for f in subject.fields
    ]
    
    subject_detail = SubjectDetailResponse(
        id=subject.id,
        name=subject.name,
        description=subject.description,
        icon_name=subject.icon_name,
        icon_color=subject.icon_color,
        did=subject.did,
        is_active=subject.is_active,
        fields=field_responses,
        created_at=subject.created_at,
    )
    
    return SubjectFieldListResponse(
        success=True,
        message="Subject fields retrieved successfully",
        data=subject_detail,
    )


@router.post(
    "",
    response_model=SubjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Subject",
    description="Create a new KYC document type",
    responses={
        201: {"description": "Subject created successfully"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def create_subject(
    request: CreateSubjectRequest,
    user: UserContext = Depends(get_current_user),
    service: SubjectService = Depends(get_subject_service),
) -> SubjectDetailResponse:
    """
    Create a new subject (KYC document type) for the authenticated user's use case.
    
    A DID will be automatically generated using the evrc method.
    """
    subject = service.create_subject(
        name=request.name,
        description=request.description,
        icon_name=request.icon_name,
        use_case=user.use_case,
        icon_color=request.icon_color,
    )
    
    return SubjectDetailResponse(
        id=subject.id,
        name=subject.name,
        description=subject.description,
        icon_name=subject.icon_name,
        icon_color=subject.icon_color,
        did=subject.did,
        is_active=subject.is_active,
        fields=[],
        created_at=subject.created_at,
    )


@router.post(
    "/{subject_id}/fields",
    response_model=SubjectFieldResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Subject Field",
    description="Add a new field to a subject",
    responses={
        201: {"description": "Field created successfully"},
        404: {"model": ErrorResponse, "description": "Subject not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def create_subject_field(
    subject_id: int,
    request: CreateSubjectFieldRequest,
    user: UserContext = Depends(get_current_user),
    service: SubjectService = Depends(get_subject_service),
) -> SubjectFieldResponse:
    """
    Create a new field for a subject.
    
    Fields represent extractable data points like Full Name, DOB, etc.
    Validates subject belongs to user's use case.
    """
    # Validate subject belongs to use case
    service.get_subject_by_id(subject_id=subject_id, use_case=user.use_case)
    
    field = service.create_subject_field(
        subject_id=subject_id,
        field_key=request.field_key,
        field_name=request.field_name,
        field_description=request.field_description,
        field_type=request.field_type,
        is_required=request.is_required,
        display_order=request.display_order,
    )
    
    return SubjectFieldResponse(
        id=field.id,
        field_key=field.field_key,
        field_name=field.field_name,
        field_description=field.field_description,
        field_type=field.field_type,
        is_required=field.is_required,
        display_order=field.display_order,
    )
