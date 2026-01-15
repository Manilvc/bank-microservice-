"""
Presentation Definition API endpoints.
Handles DIF Presentation Exchange operations.
"""

from typing import Optional

from fastapi import APIRouter, Depends, status, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.presentation_service import PresentationService
from app.services.s3_service import S3Service
from app.services.qr_service import QRCodeService
from app.schemas.presentation import (
    CreatePresentationRequest,
    PresentationDefinitionResponse,
    PresentationSummaryResponse,
    PresentationListResponse,
    SubmitPresentationRequest,
)
from app.services.submission_service import SubmissionService, get_submission_service
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/presentations", tags=["Presentations"])


def get_presentation_service(
    db: Session = Depends(get_db),
) -> PresentationService:
    """Dependency for PresentationService."""
    return PresentationService(
        db=db,
        s3_service=S3Service(),
        qr_service=QRCodeService(),
    )


@router.post(
    "",
    response_model=PresentationDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Presentation Definition",
    description="Create a new presentation definition with QR code",
    responses={
        201: {"description": "Presentation created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Subject or fields not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        502: {"model": ErrorResponse, "description": "S3 upload failed"},
    },
)
def create_presentation(
    request_body: CreatePresentationRequest,
    http_request: Request,
    service: PresentationService = Depends(get_presentation_service),
) -> PresentationDefinitionResponse:
    """
    Create a new presentation definition.
    
    This endpoint:
    1. Validates subject and field IDs
    2. Ensures required fields are included
    3. Generates DIF-compliant presentation definition
    4. Creates QR code and uploads to S3
    5. Stores everything in the database
    
    Returns the presentation summary with QR code URL.
    """
    # Extract base URL from request
    base_url = str(http_request.base_url).rstrip('/')
    
    presentation = service.create_presentation_definition(
        subject_id=request_body.subject_id,
        account_type=request_body.account_type,
        field_ids=request_body.field_ids,
        purpose=request_body.purpose,
        expiry_hours=request_body.expiry_hours,
        base_url=base_url,
    )
    
    requested_fields = service.get_requested_fields_info(presentation=presentation)
    
    summary = PresentationSummaryResponse(
        definition_id=presentation.definition_id,
        account_type=presentation.account_type,
        document_name=presentation.subject.name if presentation.subject else "Unknown",
        created_at=presentation.created_at,
        expires_at=presentation.expires_at,
        requested_fields=requested_fields,
        qr_code_url=presentation.qr_code_url,
        status=presentation.status,
    )
    
    return PresentationDefinitionResponse(
        success=True,
        message="Presentation definition created successfully",
        data=summary,
    )


@router.get(
    "",
    response_model=PresentationListResponse,
    summary="List Presentations",
    description="Get list of presentation definitions",
    responses={
        200: {"description": "Presentations retrieved successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def list_presentations(
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status (active, expired, completed)",
    ),
    limit: int = Query(default=50, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Skip results"),
    service: PresentationService = Depends(get_presentation_service),
) -> PresentationListResponse:
    """
    List presentation definitions with optional filtering.
    
    Supports pagination and status filtering.
    """
    presentations, total = service.list_presentations(
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    
    summaries = []
    for p in presentations:
        requested_fields = service.get_requested_fields_info(presentation=p)
        summaries.append(
            PresentationSummaryResponse(
                definition_id=p.definition_id,
                account_type=p.account_type,
                document_name=p.subject.name if p.subject else "Unknown",
                created_at=p.created_at,
                expires_at=p.expires_at,
                requested_fields=requested_fields,
                qr_code_url=p.qr_code_url,
                status=p.status,
            )
        )
    
    return PresentationListResponse(
        success=True,
        message="Presentations retrieved successfully",
        data=summaries,
        total=total,
    )


@router.get(
    "/{definition_id}",
    response_model=PresentationDefinitionResponse,
    summary="Get Presentation",
    description="Get a specific presentation definition",
    responses={
        200: {"description": "Presentation retrieved successfully"},
        404: {"model": ErrorResponse, "description": "Presentation not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_presentation(
    definition_id: str,
    service: PresentationService = Depends(get_presentation_service),
) -> PresentationDefinitionResponse:
    """
    Get a presentation definition by ID.
    
    Returns the full presentation summary including QR code URL.
    """
    presentation = service.get_presentation_by_id(definition_id=definition_id)
    requested_fields = service.get_requested_fields_info(presentation=presentation)
    
    summary = PresentationSummaryResponse(
        definition_id=presentation.definition_id,
        account_type=presentation.account_type,
        document_name=presentation.subject.name if presentation.subject else "Unknown",
        created_at=presentation.created_at,
        expires_at=presentation.expires_at,
        requested_fields=requested_fields,
        qr_code_url=presentation.qr_code_url,
        status=presentation.status,
    )
    
    return PresentationDefinitionResponse(
        success=True,
        message="Presentation retrieved successfully",
        data=summary,
    )


@router.get(
    "/{definition_id}/qr",
    summary="Get QR Code URL",
    description="Get QR code URL for a presentation",
    responses={
        200: {"description": "QR code URL retrieved"},
        404: {"model": ErrorResponse, "description": "Presentation not found"},
    },
)
def get_qr_code(
    definition_id: str,
    service: PresentationService = Depends(get_presentation_service),
) -> dict:
    """
    Get QR code URL for a presentation.
    
    Returns just the QR code URL for embedding.
    """
    presentation = service.get_presentation_by_id(definition_id=definition_id)
    
    return {
        "success": True,
        "definition_id": presentation.definition_id,
        "qr_code_url": presentation.qr_code_url,
    }


@router.get(
    "/{definition_id}/definition",
    summary="Get DIF Definition",
    description="Get the raw DIF presentation definition JSON",
    responses={
        200: {"description": "Definition retrieved"},
        404: {"model": ErrorResponse, "description": "Presentation not found"},
    },
)
def get_dif_definition(
    definition_id: str,
    service: PresentationService = Depends(get_presentation_service),
) -> dict:
    """
    Get raw DIF Presentation Definition.
    
    Returns the DIF-compliant presentation definition JSON
    that can be used by wallet applications.
    
    Structure:
    {
        "comment": "Description of the presentation",
        "presentation_definition": {
            "id": "Presentation id",
            "input_descriptors": [...]
        }
    }
    """
    presentation = service.get_presentation_by_id(definition_id=definition_id)
    
    return presentation.definition_json


@router.post(
    "/{definition_id}/submit",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Presentation",
    description="Submit a presentation for a definition (called from wallet after scanning QR)",
    responses={
        201: {"description": "Submission created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Presentation definition not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def submit_presentation(
    definition_id: str,
    request: SubmitPresentationRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Submit a presentation for a definition.
    
    This endpoint is called by wallet applications after scanning the QR code.
    It creates a submission record for review.
    """
    submission_service = get_submission_service(db=db)
    submission = submission_service.submit_presentation(
        definition_id=definition_id,
        holder_did=request.holder_did,
        submission_json=request.submission_json,
    )
    
    return {
        "success": True,
        "message": "Presentation submitted successfully",
        "data": {
            "request_id": submission.request_id,
            "definition_id": definition_id,
            "status": submission.status,
            "created_at": submission.created_at,
        },
    }
