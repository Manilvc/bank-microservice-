"""
Subject service for managing KYC document types and fields.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.subject import Subject, SubjectField
from app.exceptions.custom_exceptions import NotFoundException, DatabaseException
from app.utils.did import generate_did

logger = logging.getLogger(__name__)


class SubjectService:
    """Service for subject and field operations."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
    
    def get_all_subjects(
        self,
        active_only: bool = True,
    ) -> list[Subject]:
        """
        Get all subjects.
        
        Args:
            active_only: Filter to active subjects only
            
        Returns:
            List of Subject models
        """
        query = self.db.query(Subject)
        
        if active_only:
            query = query.filter(Subject.is_active == True)
        
        return query.order_by(Subject.id).all()
    
    def get_subject_by_id(self, subject_id: int) -> Subject:
        """
        Get subject by ID.
        
        Args:
            subject_id: Subject primary key
            
        Returns:
            Subject model
            
        Raises:
            NotFoundException: If subject not found
        """
        subject = self.db.query(Subject).filter(Subject.id == subject_id).first()
        
        if not subject:
            raise NotFoundException(
                resource="Subject",
                identifier=str(subject_id),
            )
        
        return subject
    
    def get_subject_with_fields(self, subject_id: int) -> Subject:
        """
        Get subject with all fields loaded.
        
        Args:
            subject_id: Subject primary key
            
        Returns:
            Subject model with fields
        """
        subject = self.get_subject_by_id(subject_id=subject_id)
        
        # Fields are loaded via selectin relationship
        # Sort by display_order
        subject.fields = sorted(subject.fields, key=lambda f: f.display_order)
        
        return subject
    
    def get_fields_by_ids(
        self,
        subject_id: int,
        field_ids: list[int],
    ) -> list[SubjectField]:
        """
        Get specific fields by IDs.
        
        Args:
            subject_id: Subject ID to validate fields belong to
            field_ids: List of field IDs
            
        Returns:
            List of SubjectField models
            
        Raises:
            NotFoundException: If any field not found
        """
        fields = (
            self.db.query(SubjectField)
            .filter(
                SubjectField.subject_id == subject_id,
                SubjectField.id.in_(field_ids),
                SubjectField.is_active == True,
            )
            .all()
        )
        
        found_ids = {f.id for f in fields}
        missing_ids = set(field_ids) - found_ids
        
        if missing_ids:
            raise NotFoundException(
                resource="SubjectField",
                identifier=str(list(missing_ids)),
                details=[
                    {"field": "field_ids", "message": f"Fields not found: {missing_ids}"}
                ],
            )
        
        return fields
    
    def create_subject(
        self,
        name: str,
        description: str,
        icon_name: str,
        icon_color: str = "#ffffff",
    ) -> Subject:
        """
        Create new subject.
        
        Args:
            name: Subject name
            description: Subject description
            icon_name: Icon identifier
            icon_color: Icon color hex
            
        Returns:
            Created Subject model
        """
        did = generate_did(subject_name=name)
        
        subject = Subject(
            name=name,
            description=description,
            icon_name=icon_name,
            icon_color=icon_color,
            did=did,
            is_active=True,
        )
        
        try:
            self.db.add(subject)
            self.db.commit()
            self.db.refresh(subject)
            logger.info(f"Created subject: {subject.name} with DID: {subject.did}")
            return subject
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create subject: {str(e)}")
            raise DatabaseException(
                message=f"Failed to create subject: {str(e)}",
            )
    
    def create_subject_field(
        self,
        subject_id: int,
        field_key: str,
        field_name: str,
        field_description: str,
        field_type: str = "string",
        is_required: bool = False,
        display_order: int = 0,
    ) -> SubjectField:
        """
        Create field for a subject.
        
        Args:
            subject_id: Subject ID
            field_key: Machine-readable key
            field_name: Human-readable name
            field_description: Field description
            field_type: Data type
            is_required: Whether mandatory
            display_order: UI display order
            
        Returns:
            Created SubjectField model
        """
        # Verify subject exists
        self.get_subject_by_id(subject_id=subject_id)
        
        field = SubjectField(
            subject_id=subject_id,
            field_key=field_key,
            field_name=field_name,
            field_description=field_description,
            field_type=field_type,
            is_required=is_required,
            display_order=display_order,
            is_active=True,
        )
        
        try:
            self.db.add(field)
            self.db.commit()
            self.db.refresh(field)
            logger.info(f"Created field: {field.field_name} for subject: {subject_id}")
            return field
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create field: {str(e)}")
            raise DatabaseException(
                message=f"Failed to create field: {str(e)}",
            )


def get_subject_service(db: Session) -> SubjectService:
    """Factory function for SubjectService."""
    return SubjectService(db=db)
