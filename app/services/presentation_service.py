"""
Presentation Definition service.
Handles DIF Presentation Exchange operations.
"""

from __future__ import annotations

import json
import logging
import re
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
        use_case: str,
        purpose: Optional[str] = None,
        expiry_hours: Optional[int] = None,
        base_url: Optional[str] = None,
    ) -> PresentationDefinition:
        """
        Create a new presentation definition.
        
        Args:
            subject_id: Subject/document type ID
            account_type: Type of account (e.g., Savings Account)
            field_ids: List of field IDs to request
            use_case: Use case identifier (bank, hotel, etc.)
            purpose: Purpose description
            expiry_hours: Hours until expiration
            base_url: Base URL for API endpoints (extracted from request if not provided)
            
        Returns:
            Created PresentationDefinition model
        """
        # Get subject with fields loaded, validate it belongs to use_case
        subject = self.subject_service.get_subject_with_fields(subject_id=subject_id)
        
        # Validate subject belongs to the specified use_case
        if subject.use_case.lower() != use_case.lower():
            raise PresentationException(
                message=f"Subject does not belong to use case '{use_case}'",
                details=[{
                    "field": "subject_id",
                    "message": f"Subject belongs to '{subject.use_case}', not '{use_case}'",
                    "code": "use_case_mismatch",
                }],
            )
        
        # Get all fields (user-selected + required)
        fields = self.subject_service.get_fields_by_ids(
            subject_id=subject_id,
            field_ids=list(field_ids),
        )
        
        # # Validate required fields are included (should always pass now, but kept for safety)
        # self._validate_required_fields(subject=subject, selected_fields=fields)
        
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
        
        # Use provided base_url or fall back to settings
        api_base_url = base_url or settings.api_url
        
        # Generate QR code with URL-based approach (minimal data)
        submission_url = f"{api_base_url}/api/v1/presentations/{definition_id}/submit"
        definition_url = f"{api_base_url}/api/v1/presentations/{definition_id}/definition"
        
        # Minimal QR data with URL to fetch full definition
        qr_data = {
            "type": "presentation_request",
            "definition_id": definition_id,
            "definition_url": definition_url,
            "submission_url": submission_url,
            "callback_url": submission_url,
            "account_type": account_type,
            "purpose": purpose or f"KYC verification for {account_type}",
            "expires_at": expires_at.isoformat(),
        }
        
        # Upload JSON data to S3
        json_s3_key = f"qr-data/presentations/{definition_id}.json"
        json_url = self.s3_service.upload_json(
            json_data=qr_data,
            s3_key=json_s3_key,
        )
        logger.info(f"Uploaded QR data JSON to S3: {json_s3_key} -> {json_url}")
        
        # Generate QR code with S3 JSON URL
        qr_bytes = self.qr_service.generate_qr_bytes(data=json_url)
        logger.info(f"QR code generated with S3 JSON URL for definition: {definition_id}")
        
        # Upload QR image to S3
        qr_s3_key = f"qr-codes/presentations/{definition_id}.png"
        qr_url = self.s3_service.upload_image(
            image_bytes=qr_bytes,
            s3_key=qr_s3_key,
        )
        
        # Create database record
        presentation = PresentationDefinition(
            definition_id=definition_id,
            name=f"{subject.name} Verification",
            purpose=purpose,
            subject_id=subject_id,
            use_case=use_case.lower(),
            account_type=account_type,
            requested_fields=requested_fields_data,
            definition_json=dif_definition,
            qr_code_s3_key=qr_s3_key,
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
            # Cleanup S3 on failure (both JSON and QR image)
            try:
                self.s3_service.delete_object(s3_key=json_s3_key)
            except Exception:
                pass
            try:
                self.s3_service.delete_object(s3_key=qr_s3_key)
            except Exception:
                pass
            logger.error(f"Failed to create presentation: {str(e)}")
            raise DatabaseException(
                message=f"Failed to create presentation definition: {str(e)}",
            )
    
    def get_presentation_by_id(
        self,
        definition_id: str,
        use_case: Optional[str] = None,
    ) -> PresentationDefinition:
        """
        Get presentation definition by ID, optionally filtered by use case.
        
        Args:
            definition_id: Presentation definition ID
            use_case: Use case identifier - validates presentation belongs to use case
            
        Returns:
            PresentationDefinition model
            
        Raises:
            NotFoundException: If presentation not found or doesn't match use case
        """
        query = (
            self.db.query(PresentationDefinition)
            .filter(PresentationDefinition.definition_id == definition_id)
        )
        
        if use_case:
            query = query.filter(PresentationDefinition.use_case == use_case.lower())
        
        presentation = query.first()
        
        if not presentation:
            raise NotFoundException(
                resource="PresentationDefinition",
                identifier=definition_id,
            )
        
        return presentation
    
    def list_presentations(
        self,
        use_case: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PresentationDefinition], int]:
        """
        List presentation definitions with pagination, filtered by use case.
        
        Args:
            use_case: Use case identifier (bank, hotel, etc.) - filters results
            status: Filter by status
            limit: Max results
            offset: Skip results
            
        Returns:
            Tuple of (presentations, total_count)
        """
        query = self.db.query(PresentationDefinition)
        
        if use_case:
            query = query.filter(PresentationDefinition.use_case == use_case.lower())
        
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
    
    def _camel_to_snake(self, camel_str: str) -> str:
        """
        Convert camelCase to snake_case.
        
        Args:
            camel_str: camelCase string
            
        Returns:
            snake_case string
        """
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def _snake_to_camel(self, snake_str: str) -> str:
        """
        Convert snake_case to camelCase.
        
        Args:
            snake_str: snake_case string
            
        Returns:
            camelCase string
        """
        components = snake_str.split('_')
        return components[0] + ''.join(x.capitalize() for x in components[1:])
    
    def _generate_key_variations(self, field_key: str) -> list[str]:
        """
        Dynamically generate key variations from field_key.
        
        Creates variations by converting between naming conventions
        and extracting common abbreviations.
        
        Args:
            field_key: The original field key
            
        Returns:
            List of key variations (original first)
        """
        if not field_key or not field_key.strip():
            return []
        
        # Clean the field_key (remove trailing/leading whitespace and underscores)
        field_key = field_key.strip().rstrip('_').lstrip('_')
        if not field_key:
            return []
        
        variations = [field_key]
        
        # Check if it's camelCase (has uppercase in middle)
        has_camel = any(c.isupper() for c in field_key[1:]) if len(field_key) > 1 else False
        # Check if it's snake_case
        has_snake = '_' in field_key
        
        # Generate snake_case from camelCase
        if has_camel and not has_snake:
            snake_version = self._camel_to_snake(field_key)
            if snake_version != field_key.lower() and snake_version not in variations:
                variations.append(snake_version)
        
        # Generate camelCase from snake_case
        if has_snake:
            camel_version = self._snake_to_camel(field_key)
            if camel_version != field_key and camel_version not in variations:
                variations.append(camel_version)
        
        # Generate lowercase version
        lower_version = field_key.lower()
        if lower_version not in variations:
            variations.append(lower_version)
        
        # Extract potential abbreviations from camelCase words
        if has_camel:
            words = re.findall('[A-Z][a-z]*', field_key)
            if len(words) > 1:
                # Create abbreviation from first letters
                abbrev = ''.join(w[0].lower() for w in words)
                if abbrev not in variations and len(abbrev) >= 2:
                    variations.append(abbrev)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for var in variations:
            if var and var not in seen:
                seen.add(var)
                unique_variations.append(var)
        
        return unique_variations if unique_variations else [field_key]
    
    def _generate_path_variations(self, field_key: str) -> list[str]:
        """
        Generate path variations for a field key dynamically.
        
        Creates multiple path variations to support different credential formats.
        All variations are generated dynamically from the field_key.
        
        Args:
            field_key: The field key identifier
            
        Returns:
            List of path strings with original field_key prioritized
        """
        
        # Generate paths for each variation
        # Format: $.credentialSubject.{key} and $.vc.credentialSubject.{key}
        path_list = []
        
        path_list.append(f"$.credentialSubject.{field_key}")
        path_list.append(f"$.vc.credentialSubject.{field_key}")
        
        return path_list
    
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
            DIF-compliant presentation definition dict with comment and presentation_definition wrapper
        """
        input_descriptors = []
        path_list = []
        
        for field in fields:
            # Generate path variations for each field
            path_list.append(f"$.credentialSubject.{field.field_key}")
            path_list.append(f"$.vc.credentialSubject.{field.field_key}")

        descriptor = {
            "id": subject.did,
            "name": subject.name,
            "purpose": purpose or subject.description,
            "constraints": {
                "fields": [
                    {
                        "path": path_list,
                    }
                ],
            },
        }
            
        input_descriptors.append(descriptor)
        
        # Build the inner presentation definition
        inner_definition = {
            "id": definition_id,
            "input_descriptors": input_descriptors,
        }
        
        # Wrap with comment and presentation_definition
        return {
            "comment": purpose or f"KYC verification for {subject.name}",
            "presentation_definition": inner_definition,
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
