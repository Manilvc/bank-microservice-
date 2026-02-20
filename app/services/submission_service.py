"""
Submission service for handling presentation submissions.
Manages submission creation, listing, and status updates.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, and_, or_, String, cast, text
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
    
    def get_submission_by_id(
        self,
        request_id: str,
        use_case: Optional[str] = None,
    ) -> PresentationRequest:
        """
        Get submission by request ID, optionally filtered by use case.
        
        Args:
            request_id: Submission request ID
            use_case: Use case identifier - validates submission belongs to use case
            
        Returns:
            PresentationRequest model
            
        Raises:
            NotFoundException: If submission not found or doesn't match use case
        """
        query = (
            self.db.query(PresentationRequest)
            .join(PresentationDefinition)
            .filter(PresentationRequest.request_id == request_id)
        )
        
        if use_case:
            query = query.filter(PresentationDefinition.use_case == use_case.lower())
        
        submission = query.first()
        
        if not submission:
            raise NotFoundException(
                resource="PresentationRequest",
                identifier=request_id,
            )
        
        return submission
    
    def list_submissions(
        self,
        use_case: Optional[str] = None,
        status: Optional[str] = None,
        account_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PresentationRequest], int]:
        """
        List submissions with filtering, search, and pagination, filtered by use case.
        
        Args:
            use_case: Use case identifier (bank, hotel, etc.) - filters results
            status: Filter by status (pending, approved, rejected)
            account_type: Filter by account type
            search: Search by name or document (searches in submission_json and document name)
            limit: Max results
            offset: Skip results
            
        Returns:
            Tuple of (submissions, total_count)
        """
        from app.models.subject import Subject
        
        query = (
            self.db.query(PresentationRequest)
            .join(PresentationDefinition)
            .outerjoin(Subject, PresentationDefinition.subject_id == Subject.id)
        )
        
        # Apply filters
        if use_case:
            query = query.filter(PresentationDefinition.use_case == use_case.lower())
        
        if status:
            query = query.filter(PresentationRequest.status == status)
        
        if account_type:
            query = query.filter(PresentationDefinition.account_type == account_type)
        
        # Apply search filter
        if search:
            search_term = f"%{search.lower()}%"
            # Search in document name, submission_json, and holder_did
            query = query.filter(
                or_(
                    func.lower(Subject.name).like(search_term),
                    # Search in submission_json (cast to text and search)
                    cast(PresentationRequest.submission_json, String).ilike(search_term),
                    # Search in holder_did
                    func.lower(cast(PresentationRequest.holder_did, String)).like(search_term),
                )
            )
        
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
    
    def get_dashboard_statistics(self, use_case: Optional[str] = None) -> dict:
        """
        Get dashboard statistics filtered by use case.
        
        Args:
            use_case: Use case identifier (bank, hotel, etc.) - filters statistics
            
        Returns:
            Dictionary with statistics
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        
        # Base query for submissions with use_case filter
        submission_query = (
            self.db.query(PresentationRequest)
            .join(PresentationDefinition)
        )
        
        if use_case:
            submission_query = submission_query.filter(
                PresentationDefinition.use_case == use_case.lower()
            )
        
        # Count pending reviews
        pending_count = (
            submission_query.filter(PresentationRequest.status == "pending")
            .count() or 0
        )
        
        # Count pending today
        pending_today = (
            submission_query.filter(
                and_(
                    PresentationRequest.status == "pending",
                    PresentationRequest.created_at >= today_start,
                )
            )
            .count() or 0
        )
        
        # Count approved
        approved_count = (
            submission_query.filter(PresentationRequest.status == "approved")
            .count() or 0
        )
        
        # Count approved this week
        approved_this_week = (
            submission_query.filter(
                and_(
                    PresentationRequest.status == "approved",
                    PresentationRequest.completed_at >= week_start,
                )
            )
            .count() or 0
        )
        
        # Count rejected
        rejected_count = (
            submission_query.filter(PresentationRequest.status == "rejected")
            .count() or 0
        )
        
        # Count active QR definitions
        qr_query = self.db.query(func.count(PresentationDefinition.id)).filter(
            PresentationDefinition.status == "active"
        )
        
        if use_case:
            qr_query = qr_query.filter(PresentationDefinition.use_case == use_case.lower())
        
        qr_definitions_count = qr_query.scalar() or 0
        
        return {
            "pending_reviews": pending_count,
            "approved": approved_count,
            "rejected": rejected_count,
            "qr_definitions": qr_definitions_count,
            "pending_today": pending_today,
            "approved_this_week": approved_this_week,
        }
    
    def get_recent_activity(
        self,
        use_case: Optional[str] = None,
        limit: int = 10,
    ) -> list[PresentationRequest]:
        """
        Get recent submission activity filtered by use case.
        
        Args:
            use_case: Use case identifier (bank, hotel, etc.) - filters results
            limit: Number of recent submissions to return
            
        Returns:
            List of recent PresentationRequest models
        """
        query = (
            self.db.query(PresentationRequest)
            .join(PresentationDefinition)
        )
        
        if use_case:
            query = query.filter(PresentationDefinition.use_case == use_case.lower())
        
        submissions = (
            query.order_by(PresentationRequest.created_at.desc())
            .limit(limit)
            .all()
        )
        
        return submissions


def extract_holder_name(submission_json: Optional[dict]) -> Optional[str]:
    """
    Extract holder name from submission JSON.
    
    Looks for name in credentialSubject or top-level.
    
    Args:
        submission_json: Submission data dictionary
        
    Returns:
        Holder name or None
    """
    if not submission_json:
        return None
    
    # Try credentialSubject.name first
    credential_subject = submission_json.get("credentialSubject", {})
    if isinstance(credential_subject, dict):
        name = credential_subject.get("name") or credential_subject.get("full_name") or credential_subject.get("fullName")
        if name:
            return str(name)
    
    # Try top-level name
    name = submission_json.get("name") or submission_json.get("full_name") or submission_json.get("fullName")
    if name:
        return str(name)
    
    return None


def extract_fields_from_submission(
    submission_json: Optional[dict],
    requested_fields: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Extract fields from submission JSON for display.
    
    Args:
        submission_json: Submission data dictionary
        requested_fields: List of requested field definitions
        
    Returns:
        List of extracted fields with key, name, and value
    """
    if not submission_json:
        return []
    
    extracted = []
    credential_subject = submission_json.get("credentialSubject", {})
    
    if not isinstance(credential_subject, dict):
        return []
    
    # If requested_fields provided, extract those specific fields
    if requested_fields:
        for field_def in requested_fields:
            field_key = field_def.get("field_key") or field_def.get("field_id")
            field_name = field_def.get("field_name", field_key)
            value = credential_subject.get(field_key)
            
            if value is not None:
                extracted.append({
                    "key": field_key,
                    "name": field_name,
                    "value": str(value),
                })
    else:
        # Extract all fields from credentialSubject
        for key, value in credential_subject.items():
            if value is not None:
                extracted.append({
                    "key": key,
                    "name": key.replace("_", " ").title(),
                    "value": str(value),
                })
    
    return extracted


def format_relative_time(dt: datetime) -> str:
    """
    Format datetime as relative time string.
    
    Args:
        dt: Datetime to format
        
    Returns:
        Relative time string (e.g., "25 min ago", "2 hours ago", "1 days ago")
    """
    if not dt:
        return ""
    
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    delta = now - dt
    
    if delta.days > 0:
        return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
    elif delta.seconds >= 3600:
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif delta.seconds >= 60:
        minutes = delta.seconds // 60
        return f"{minutes} min ago"
    else:
        return "just now"


def get_submission_service(db: Session) -> SubmissionService:
    """Factory function for SubmissionService."""
    return SubmissionService(db=db)
