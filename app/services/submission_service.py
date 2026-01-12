"""
Submission service for handling presentation submissions.
Manages submission creation, listing, and status updates.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.presentation import PresentationDefinition, PresentationRequest
from app.exceptions.custom_exceptions import (
    NotFoundException,
    DatabaseException,
    PresentationException,
)
from app.utils.did import generate_request_id

logger = logging.getLogger(__name__)
settings = get_settings()


class SubmissionService:
    """Service for managing presentation submissions."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
    
    def submit_presentation(
        self,
        definition_id: str,
        holder_did: Optional[str],
        submission_json: dict,
    ) -> PresentationRequest:
        """
        Submit a presentation for a definition.
        
        Args:
            definition_id: Presentation definition ID
            holder_did: Holder's DID (optional)
            submission_json: Submitted credential data
            
        Returns:
            Created PresentationRequest model
        """
        # Get presentation definition
        definition = (
            self.db.query(PresentationDefinition)
            .filter(PresentationDefinition.definition_id == definition_id)
            .first()
        )
        
        if not definition:
            raise NotFoundException(
                resource="PresentationDefinition",
                identifier=definition_id,
            )
        
        # Check if definition is expired
        if definition.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise PresentationException(
                message="Presentation definition has expired",
                details=[{
                    "field": "definition_id",
                    "message": f"Definition {definition_id} expired at {definition.expires_at}",
                    "code": "definition_expired",
                }],
            )
        
        # Check if definition is active
        if definition.status != "active":
            raise PresentationException(
                message=f"Presentation definition is not active (status: {definition.status})",
                details=[{
                    "field": "definition_id",
                    "message": f"Definition {definition_id} is not active",
                    "code": "definition_inactive",
                }],
            )
        
        # Generate request ID
        request_id = generate_request_id()
        
        # Create submission
        submission = PresentationRequest(
            request_id=request_id,
            definition_id=definition.id,
            holder_did=holder_did,
            submission_json=submission_json,
            status="pending",
        )
        
        try:
            self.db.add(submission)
            self.db.commit()
            self.db.refresh(submission)
            logger.info(f"Created submission: {request_id} for definition: {definition_id}")
            return submission
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create submission: {str(e)}")
            raise DatabaseException(
                message=f"Failed to create submission: {str(e)}",
            )
    
    def get_submission_by_id(self, request_id: str) -> PresentationRequest:
        """
        Get submission by request ID.
        
        Args:
            request_id: Submission request ID
            
        Returns:
            PresentationRequest model
        """
        submission = (
            self.db.query(PresentationRequest)
            .filter(PresentationRequest.request_id == request_id)
            .first()
        )
        
        if not submission:
            raise NotFoundException(
                resource="PresentationRequest",
                identifier=request_id,
            )
        
        return submission
    
    def list_submissions(
        self,
        status: Optional[str] = None,
        account_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PresentationRequest], int]:
        """
        List submissions with filtering and pagination.
        
        Args:
            status: Filter by status (pending, approved, rejected)
            account_type: Filter by account type
            limit: Max results
            offset: Skip results
            
        Returns:
            Tuple of (submissions, total_count)
        """
        query = (
            self.db.query(PresentationRequest)
            .join(PresentationDefinition)
        )
        
        # Apply filters
        if status:
            query = query.filter(PresentationRequest.status == status)
        
        if account_type:
            query = query.filter(PresentationDefinition.account_type == account_type)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        submissions = (
            query.order_by(PresentationRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        return submissions, total
    
    def update_submission_status(
        self,
        request_id: str,
        new_status: str,
    ) -> PresentationRequest:
        """
        Update submission status.
        
        Args:
            request_id: Submission request ID
            new_status: New status (approved, rejected)
            
        Returns:
            Updated PresentationRequest model
        """
        submission = self.get_submission_by_id(request_id=request_id)
        
        # Validate status transition
        if submission.status not in ["pending"]:
            raise PresentationException(
                message=f"Cannot update status from {submission.status} to {new_status}",
                details=[{
                    "field": "status",
                    "message": f"Only pending submissions can be updated",
                    "code": "invalid_status_transition",
                }],
            )
        
        if new_status not in ["approved", "rejected"]:
            raise PresentationException(
                message=f"Invalid status: {new_status}",
                details=[{
                    "field": "status",
                    "message": "Status must be 'approved' or 'rejected'",
                    "code": "invalid_status",
                }],
            )
        
        # Update status
        submission.status = new_status
        submission.completed_at = datetime.now(timezone.utc)
        
        try:
            self.db.commit()
            self.db.refresh(submission)
            logger.info(f"Updated submission {request_id} status to {new_status}")
            return submission
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update submission status: {str(e)}")
            raise DatabaseException(
                message=f"Failed to update submission status: {str(e)}",
            )
    
    def get_dashboard_statistics(self) -> dict:
        """
        Get dashboard statistics.
        
        Returns:
            Dictionary with statistics
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        
        # Count pending reviews
        pending_count = (
            self.db.query(func.count(PresentationRequest.id))
            .filter(PresentationRequest.status == "pending")
            .scalar() or 0
        )
        
        # Count pending today
        pending_today = (
            self.db.query(func.count(PresentationRequest.id))
            .filter(
                and_(
                    PresentationRequest.status == "pending",
                    PresentationRequest.created_at >= today_start,
                )
            )
            .scalar() or 0
        )
        
        # Count approved
        approved_count = (
            self.db.query(func.count(PresentationRequest.id))
            .filter(PresentationRequest.status == "approved")
            .scalar() or 0
        )
        
        # Count approved this week
        approved_this_week = (
            self.db.query(func.count(PresentationRequest.id))
            .filter(
                and_(
                    PresentationRequest.status == "approved",
                    PresentationRequest.completed_at >= week_start,
                )
            )
            .scalar() or 0
        )
        
        # Count rejected
        rejected_count = (
            self.db.query(func.count(PresentationRequest.id))
            .filter(PresentationRequest.status == "rejected")
            .scalar() or 0
        )
        
        # Count active QR definitions
        qr_definitions_count = (
            self.db.query(func.count(PresentationDefinition.id))
            .filter(PresentationDefinition.status == "active")
            .scalar() or 0
        )
        
        return {
            "pending_reviews": pending_count,
            "approved": approved_count,
            "rejected": rejected_count,
            "qr_definitions": qr_definitions_count,
            "pending_today": pending_today,
            "approved_this_week": approved_this_week,
        }
    
    def get_recent_activity(self, limit: int = 10) -> list[PresentationRequest]:
        """
        Get recent submission activity.
        
        Args:
            limit: Number of recent submissions to return
            
        Returns:
            List of recent PresentationRequest models
        """
        submissions = (
            self.db.query(PresentationRequest)
            .join(PresentationDefinition)
            .order_by(PresentationRequest.created_at.desc())
            .limit(limit)
            .all()
        )
        
        return submissions


def get_submission_service(db: Session) -> SubmissionService:
    """Factory function for SubmissionService."""
    return SubmissionService(db=db)
