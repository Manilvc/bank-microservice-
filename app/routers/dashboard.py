"""
Dashboard API endpoints.
Provides statistics and recent activity for the dashboard.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.submission_service import SubmissionService
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
    service: SubmissionService = Depends(get_submission_service),
) -> DashboardStatisticsResponse:
    """
    Get dashboard statistics.
    
    Returns counts for:
    - Pending reviews
    - Approved submissions
    - Rejected submissions
    - Active QR definitions
    - Pending today
    - Approved this week
    """
    stats = service.get_dashboard_statistics()
    
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
    service: SubmissionService = Depends(get_submission_service),
) -> RecentActivityResponse:
    """
    Get recent submission activity.
    
    Returns the most recent submissions ordered by creation time.
    """
    submissions = service.get_recent_activity(limit=limit)
    
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
    
    return RecentActivityResponse(
        success=True,
        message="Recent activity retrieved successfully",
        data=submission_responses,
    )
