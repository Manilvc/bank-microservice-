"""
Presentation Definition service.
Handles DIF Presentation Exchange operations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.presentation import PresentationDefinition, PresentationRequest
from app.models.subject import Subject, SubjectField
from app.exceptions.custom_exceptions import (
    NotFoundException,
    DatabaseException,
    PresentationException,
)
from app.services.s3_service import S3Service
from app.services.qr_service import QRCodeService
from app.services.subject_service import SubjectService
from app.utils.did import generate_presentation_id, generate_request_id
from app.schemas.presentation import RequestedFieldInfo

logger = logging.getLogger(__name__)
settings = get_settings()


class PresentationService:
    """Service for presentation definition operations."""
    
    def __init__(
        self,
        db: Session,
        s3_service: S3Service,
        qr_service: QRCodeService,
    ):
        """Initialize with dependencies."""
        self.db = db
        self.s3_service = s3_service
        self.qr_service = qr_service
        self.subject_service = SubjectService(db=db)
    
    def create_presentation_definition(
        self,
        subject_id: int,
        account_type: str,
        field_ids: list[int],
        purpose: Optional[str] = None,
        expiry_hours: Optional[int] = None,
    ) -> PresentationDefinition:
        """
        Create a new presentation definition.
        
        Args:
            subject_id: Subject/document type ID
            account_type: Type of account (e.g., Savings Account)
            field_ids: List of field IDs to request
            purpose: Purpose description
            expiry_hours: Hours until expiration
            
        Returns:
            Created PresentationDefinition model
        """
        # Get subject with fields loaded
        subject = self.subject_service.get_subject_with_fields(subject_id=subject_id)
        
        # Get required field IDs
        required_field_ids = {f.id for f in subject.fields if f.is_required and f.is_active}
        
        # Automatically include required fields if not already present
        all_field_ids = set(field_ids) | required_field_ids
        
        # Get all fields (user-selected + required)
        fields = self.subject_service.get_fields_by_ids(
            subject_id=subject_id,
            field_ids=list(all_field_ids),
        )
        
        # Validate required fields are included (should always pass now, but kept for safety)
        self._validate_required_fields(subject=subject, selected_fields=fields)
        
        # Generate IDs and timestamps
        definition_id = generate_presentation_id()
        expiry = expiry_hours or settings.presentation_expiry_hours
        expires_at = datetime.utcnow() + timedelta(hours=expiry)
        
        # Build DIF presentation definition
        dif_definition = self._build_dif_definition(
            definition_id=definition_id,
            subject=subject,
            fields=fields,
            purpose=purpose or f"KYC verification for {account_type}",
        )
        
        # Build requested fields info
        requested_fields_data = [
            {
                "field_id": f.id,
                "field_key": f.field_key,
                "field_name": f.field_name,
                "is_required": f.is_required,
            }
            for f in fields
        ]
        
        # Generate QR code with complete data
        submission_url = f"{settings.api_url}/api/v1/presentations/{definition_id}/submit"
        definition_url = f"{settings.api_url}/api/v1/presentations/{definition_id}/definition"
        
        # Try full data first
        qr_data = {
            "type": "presentation_request",
            "definition_id": definition_id,
            "presentation_definition": dif_definition,
            "submission_url": submission_url,
            "callback_url": submission_url,  # Backward compatibility
            "subject": {
                "id": subject.id,
                "name": subject.name,
                "description": subject.description,
            },
            "account_type": account_type,
            "purpose": purpose or f"KYC verification for {account_type}",
            "expires_at": expires_at.isoformat(),
            "requested_fields": requested_fields_data,
        }
        
        # Try to generate QR code with full data
        try:
            qr_bytes = self.qr_service.generate_qr_bytes(data=qr_data)
            logger.info(f"QR code generated with full data for definition: {definition_id}")
        except ValueError as e:
            # If data is too large, use URL-based approach
            if "too large" in str(e).lower() or "version" in str(e).lower():
                logger.warning(
                    f"QR code data too large for definition {definition_id}. "
                    f"Falling back to URL-based approach."
                )
                # Minimal QR data with URL to fetch full definition
                qr_data = {
                    "type": "presentation_request",
                    "definition_id": definition_id,
                    "definition_url": definition_url,  # URL to fetch full definition
                    "submission_url": submission_url,
                    "callback_url": submission_url,
                    "account_type": account_type,
                    "purpose": purpose or f"KYC verification for {account_type}",
                    "expires_at": expires_at.isoformat(),
                }
                qr_bytes = self.qr_service.generate_qr_bytes(data=qr_data)
                logger.info(f"QR code generated with URL-based approach for definition: {definition_id}")
            else:
                raise
        
        # Upload QR to S3
        s3_key = f"qr-codes/presentations/{definition_id}.png"
        qr_url = self.s3_service.upload_image(
            image_bytes=qr_bytes,
            s3_key=s3_key,
        )
        
        # Create database record
        presentation = PresentationDefinition(
            definition_id=definition_id,
            name=f"{subject.name} Verification",
            purpose=purpose,
            subject_id=subject_id,
            account_type=account_type,
            requested_fields=requested_fields_data,
            definition_json=dif_definition,
            qr_code_s3_key=s3_key,
            qr_code_url=qr_url,
            status="active",
            expires_at=expires_at,
        )
        
        try:
            self.db.add(presentation)
            self.db.commit()
            self.db.refresh(presentation)
            logger.info(f"Created presentation definition: {definition_id}")
            return presentation
            
        except Exception as e:
            self.db.rollback()
            # Cleanup S3 on failure
            try:
                self.s3_service.delete_object(s3_key=s3_key)
            except Exception:
                pass
            logger.error(f"Failed to create presentation: {str(e)}")
            raise DatabaseException(
                message=f"Failed to create presentation definition: {str(e)}",
            )
    
    def get_presentation_by_id(self, definition_id: str) -> PresentationDefinition:
        """
        Get presentation definition by ID.
        
        Args:
            definition_id: Presentation definition ID
            
        Returns:
            PresentationDefinition model
        """
        presentation = (
            self.db.query(PresentationDefinition)
            .filter(PresentationDefinition.definition_id == definition_id)
            .first()
        )
        
        if not presentation:
            raise NotFoundException(
                resource="PresentationDefinition",
                identifier=definition_id,
            )
        
        return presentation
    
    def list_presentations(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PresentationDefinition], int]:
        """
        List presentation definitions with pagination.
        
        Args:
            status: Filter by status
            limit: Max results
            offset: Skip results
            
        Returns:
            Tuple of (presentations, total_count)
        """
        query = self.db.query(PresentationDefinition)
        
        if status:
            query = query.filter(PresentationDefinition.status == status)
        
        total = query.count()
        presentations = (
            query.order_by(PresentationDefinition.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        return presentations, total
    
    def get_requested_fields_info(
        self,
        presentation: PresentationDefinition,
    ) -> list[RequestedFieldInfo]:
        """
        Get requested fields info from presentation.
        
        Args:
            presentation: PresentationDefinition model
            
        Returns:
            List of RequestedFieldInfo
        """
        return [
            RequestedFieldInfo(
                field_id=f["field_id"],
                field_key=f["field_key"],
                field_name=f["field_name"],
                is_required=f["is_required"],
            )
            for f in presentation.requested_fields
        ]
    
    def _validate_required_fields(
        self,
        subject: Subject,
        selected_fields: list[SubjectField],
    ) -> None:
        """
        Validate that all required fields are selected.
        
        Raises:
            PresentationException: If required fields missing
        """
        required_field_ids = {f.id for f in subject.fields if f.is_required and f.is_active}
        selected_ids = {f.id for f in selected_fields}
        
        missing_required = required_field_ids - selected_ids
        
        if missing_required:
            missing_fields = [
                f for f in subject.fields if f.id in missing_required
            ]
            missing_names = [f.field_name for f in missing_fields]
            missing_ids = [f.id for f in missing_fields]
            raise PresentationException(
                message=f"Required fields missing: {', '.join(missing_names)} (IDs: {', '.join(map(str, missing_ids))})",
                details=[
                    {
                        "field": "field_ids",
                        "message": f"Missing required field: {field.field_name} (ID: {field.id})",
                        "code": "required_field_missing",
                        "field_id": field.id,
                        "field_name": field.field_name,
                    }
                    for field in missing_fields
                ],
            )
    
    def _build_dif_definition(
        self,
        definition_id: str,
        subject: Subject,
        fields: list[SubjectField],
        purpose: str,
    ) -> dict:
        """
        Build DIF Presentation Exchange definition.
        
        Args:
            definition_id: Unique definition ID
            subject: Subject model
            fields: List of requested fields
            purpose: Purpose description
            
        Returns:
            DIF-compliant presentation definition dict
        """
        input_descriptors = []
        
        for field in fields:
            descriptor = {
                "id": field.field_key,
                "name": field.field_name,
                "purpose": field.field_description,
                "constraints": {
                    "fields": [
                        {
                            "path": [f"$.credentialSubject.{field.field_key}"],
                            "purpose": field.field_description,
                        }
                    ]
                },
            }
            
            if field.is_required:
                descriptor["constraints"]["fields"][0]["filter"] = {
                    "type": field.field_type,
                }
            
            input_descriptors.append(descriptor)
        
        return {
            "id": definition_id,
            "name": f"{subject.name} Verification",
            "purpose": purpose,
            "format": {
                "ldp_vc": {
                    "proof_type": ["Ed25519Signature2020"],
                }
            },
            "input_descriptors": input_descriptors,
        }


def get_presentation_service(
    db: Session,
    s3_service: Optional[S3Service] = None,
    qr_service: Optional[QRCodeService] = None,
) -> PresentationService:
    """Factory function for PresentationService."""
    return PresentationService(
        db=db,
        s3_service=s3_service or S3Service(),
        qr_service=qr_service or QRCodeService(),
    )
