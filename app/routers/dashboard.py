"""
Dashboard API endpoints.
Provides statistics and recent activity for the dashboard.
"""

from fastapi import APIRouter, Depends, Query
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
    DashboardStatisticsResponse,
    RecentActivityResponse,
    SubmissionResponse,
)
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_submission_service(
    db: Session = Depends(get_db),
) -> SubmissionService:
    """Dependency for SubmissionService."""
    from app.services.submission_service import get_submission_service as _get_service
    return _get_service(db=db)


@router.get(
    "/statistics",
    response_model=DashboardStatisticsResponse,
    summary="Get Dashboard Statistics",
    description="Get statistics for the dashboard (pending, approved, rejected, QR definitions)",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_dashboard_statistics(
    user: UserContext = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service),
) -> DashboardStatisticsResponse:
    """
    Get dashboard statistics for the authenticated user's use case.
    
    Returns counts for:
    - Pending reviews
    - Approved submissions
    - Rejected submissions
    - Active QR definitions
    - Pending today
    - Approved this week
    """
    stats = service.get_dashboard_statistics(use_case=user.use_case)
    
    return DashboardStatisticsResponse(
        success=True,
        message="Statistics retrieved successfully",
        data=stats,
    )


@router.get(
    "/recent-activity",
    response_model=RecentActivityResponse,
    summary="Get Recent Activity",
    description="Get recent submission activity",
    responses={
        200: {"description": "Recent activity retrieved successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_recent_activity(
    limit: int = Query(default=10, ge=1, le=50, description="Number of recent submissions"),
    user: UserContext = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service),
) -> RecentActivityResponse:
    """
    Get recent submission activity for the authenticated user's use case.
    
    Returns the most recent submissions ordered by creation time.
    """
    submissions = service.get_recent_activity(
        use_case=user.use_case,
        limit=limit,
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
                status=sub.status.upper(),
                created_at=sub.created_at,
                completed_at=sub.completed_at,
                submission_json=sub.submission_json,
                holder_name=holder_name,
                submitted_ago=submitted_ago,
                extracted_fields=extracted_fields,
            )
        )
    
    return RecentActivityResponse(
        success=True,
        message="Recent activity retrieved successfully",
        data=submission_responses,
    )
