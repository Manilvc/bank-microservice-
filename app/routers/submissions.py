"""
Submission API endpoints.
Handles presentation submission operations.
"""

from typing import Optional

from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import get_current_user
from app.schemas.auth import UserContext
from app.services.submission_service import (
    SubmissionService,
    extract_holder_name,
    extract_fields_from_submission,
    format_relative_time,
)
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
    user: UserContext = Depends(get_current_user),
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
    # Validate definition belongs to use case before submission
    from app.services.presentation_service import PresentationService
    from app.services.s3_service import S3Service
    from app.services.qr_service import QRCodeService
    
    db_session = next(get_db())
    try:
        pres_service = PresentationService(
            db=db_session,
            s3_service=S3Service(),
            qr_service=QRCodeService(),
        )
        pres_service.get_presentation_by_id(
            definition_id=definition_id,
            use_case=user.use_case,
        )
    finally:
        db_session.close()
    
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
    search: Optional[str] = Query(
        default=None,
        description="Search by name or document",
    ),
    limit: int = Query(default=50, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Skip results"),
    user: UserContext = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service),
) -> SubmissionListResponse:
    """
    List submissions with optional filtering and search for the authenticated user's use case.
    
    Supports:
    - Filtering by status and account type
    - Searching by name or document name
    - Pagination
    """
    submissions, total = service.list_submissions(
        use_case=user.use_case,
        status=status_filter,
        account_type=account_type,
        search=search,
        limit=limit,
        offset=offset,
    )
    
    submission_responses = []
    for sub in submissions:
        # Extract holder name
        holder_name = extract_holder_name(sub.submission_json)
        
        # Extract fields for display
        requested_fields = sub.definition.requested_fields if hasattr(sub.definition, 'requested_fields') else None
        extracted_fields = extract_fields_from_submission(
            submission_json=sub.submission_json,
            requested_fields=requested_fields,
        )
        
        # Format relative time
        submitted_ago = format_relative_time(sub.created_at)
        
        submission_responses.append(
            SubmissionResponse(
                request_id=sub.request_id,
                definition_id=sub.definition.definition_id,
                account_type=sub.definition.account_type,
                document_name=sub.definition.subject.name if sub.definition.subject else "Unknown",
                holder_did=sub.holder_did,
                status=sub.status.upper(),  # Uppercase for UI (PENDING, APPROVED, REJECTED)
                created_at=sub.created_at,
                completed_at=sub.completed_at,
                submission_json=sub.submission_json,
                holder_name=holder_name,
                submitted_ago=submitted_ago,
                extracted_fields=extracted_fields,
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
    user: UserContext = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service),
) -> dict:
    """
    Get a submission by request ID for the authenticated user's use case.
    
    Returns the full submission details including submitted data.
    """
    submission = service.get_submission_by_id(
        request_id=request_id,
        use_case=user.use_case,
    )
    
    # Extract holder name
    holder_name = extract_holder_name(submission.submission_json)
    
    # Extract fields for display
    requested_fields = submission.definition.requested_fields if hasattr(submission.definition, 'requested_fields') else None
    extracted_fields = extract_fields_from_submission(
        submission_json=submission.submission_json,
        requested_fields=requested_fields,
    )
    
    # Format relative time
    submitted_ago = format_relative_time(submission.created_at)
    
    return {
        "success": True,
        "message": "Submission retrieved successfully",
        "data": SubmissionResponse(
            request_id=submission.request_id,
            definition_id=submission.definition.definition_id,
            account_type=submission.definition.account_type,
            document_name=submission.definition.subject.name if submission.definition.subject else "Unknown",
            holder_did=submission.holder_did,
            status=submission.status.upper(),
            created_at=submission.created_at,
            completed_at=submission.completed_at,
            submission_json=submission.submission_json,
            holder_name=holder_name,
            submitted_ago=submitted_ago,
            extracted_fields=extracted_fields,
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
    user: UserContext = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service),
) -> dict:
    """
    Update submission status for the authenticated user's use case.
    
    Allows approving or rejecting a pending submission.
    Only pending submissions can be updated.
    """
    # Validate submission belongs to use case
    service.get_submission_by_id(
        request_id=request_id,
        use_case=user.use_case,
    )
    
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
