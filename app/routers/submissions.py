"""
Submission API endpoints.
Handles presentation submission operations.
"""

from typing import Optional

from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.submission_service import SubmissionService
from app.schemas.presentation import (
    SubmitPresentationRequest,
    SubmissionResponse,
    SubmissionListResponse,
    UpdateSubmissionStatusRequest,
)
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/submissions", tags=["Submissions"])


def get_submission_service(
    db: Session = Depends(get_db),
) -> SubmissionService:
    """Dependency for SubmissionService."""
    from app.services.submission_service import get_submission_service as _get_service
    return _get_service(db=db)


@router.post(
    "/{definition_id}/submit",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Presentation",
    description="Submit a presentation for a definition",
    responses={
        201: {"description": "Submission created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Presentation definition not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def submit_presentation(
    definition_id: str = Path(description="Presentation definition ID"),
    request: SubmitPresentationRequest = ...,
    service: SubmissionService = Depends(get_submission_service),
) -> dict:
    """
    Submit a presentation for a definition.
    
    This endpoint:
    1. Validates the definition exists and is active
    2. Checks if definition has expired
    3. Creates a submission record
    4. Returns the submission details
    """
    submission = service.submit_presentation(
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


@router.get(
    "",
    response_model=SubmissionListResponse,
    summary="List Submissions",
    description="Get list of submissions with filtering",
    responses={
        200: {"description": "Submissions retrieved successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def list_submissions(
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status (pending, approved, rejected)",
    ),
    account_type: Optional[str] = Query(
        default=None,
        description="Filter by account type",
    ),
    limit: int = Query(default=50, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Skip results"),
    service: SubmissionService = Depends(get_submission_service),
) -> SubmissionListResponse:
    """
    List submissions with optional filtering.
    
    Supports filtering by status and account type, with pagination.
    """
    submissions, total = service.list_submissions(
        status=status_filter,
        account_type=account_type,
        limit=limit,
        offset=offset,
    )
    
    submission_responses = []
    for sub in submissions:
        submission_responses.append(
            SubmissionResponse(
                request_id=sub.request_id,
                definition_id=sub.definition.definition_id,
                account_type=sub.definition.account_type,
                document_name=sub.definition.subject.name if sub.definition.subject else "Unknown",
                holder_did=sub.holder_did,
                status=sub.status,
                created_at=sub.created_at,
                completed_at=sub.completed_at,
                submission_json=sub.submission_json,
            )
        )
    
    return SubmissionListResponse(
        success=True,
        message="Submissions retrieved successfully",
        data=submission_responses,
        total=total,
    )


@router.get(
    "/{request_id}",
    response_model=dict,
    summary="Get Submission",
    description="Get a specific submission by request ID",
    responses={
        200: {"description": "Submission retrieved successfully"},
        404: {"model": ErrorResponse, "description": "Submission not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_submission(
    request_id: str = Path(description="Submission request ID"),
    service: SubmissionService = Depends(get_submission_service),
) -> dict:
    """
    Get a submission by request ID.
    
    Returns the full submission details including submitted data.
    """
    submission = service.get_submission_by_id(request_id=request_id)
    
    return {
        "success": True,
        "message": "Submission retrieved successfully",
        "data": SubmissionResponse(
            request_id=submission.request_id,
            definition_id=submission.definition.definition_id,
            account_type=submission.definition.account_type,
            document_name=submission.definition.subject.name if submission.definition.subject else "Unknown",
            holder_did=submission.holder_did,
            status=submission.status,
            created_at=submission.created_at,
            completed_at=submission.completed_at,
            submission_json=submission.submission_json,
        ).model_dump(),
    }


@router.patch(
    "/{request_id}/status",
    response_model=dict,
    summary="Update Submission Status",
    description="Update submission status (approve or reject)",
    responses={
        200: {"description": "Status updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid status or transition"},
        404: {"model": ErrorResponse, "description": "Submission not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def update_submission_status(
    request_id: str = Path(description="Submission request ID"),
    request: UpdateSubmissionStatusRequest = ...,
    service: SubmissionService = Depends(get_submission_service),
) -> dict:
    """
    Update submission status.
    
    Allows approving or rejecting a pending submission.
    Only pending submissions can be updated.
    """
    submission = service.update_submission_status(
        request_id=request_id,
        new_status=request.status,
    )
    
    return {
        "success": True,
        "message": f"Submission status updated to {request.status}",
        "data": {
            "request_id": submission.request_id,
            "definition_id": submission.definition.definition_id,
            "status": submission.status,
            "completed_at": submission.completed_at,
        },
    }
