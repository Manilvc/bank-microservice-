"""
Subject and SubjectField database models.
Subjects represent KYC document types (Aadhar, PAN, Voter ID).
SubjectFields represent extractable fields from each subject.
"""

from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Subject(Base):
    """
    KYC document type model.
    Represents verification subjects like Aadhar Card, PAN Card, etc.
    """
    
    __tablename__ = "subjects"
    
    __table_args__ = (
        UniqueConstraint("name", "use_case", name="uq_subject_name_use_case"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    use_case: Mapped[str] = mapped_column(String(50), nullable=False, default="bank")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon_name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#ffffff")
    did: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    # Relationships
    fields: Mapped[List["SubjectField"]] = relationship(
        "SubjectField",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    @property
    def field_count(self) -> int:
        """Return count of available fields."""
        return len(self.fields)


class SubjectField(Base):
    """
    Field definition for a subject.
    Represents extractable data points like Full Name, DOB, Address.
    """
    
    __tablename__ = "subject_fields"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_description: Mapped[str] = mapped_column(Text, nullable=False)
    field_type: Mapped[str] = mapped_column(String(30), nullable=False, default="string")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    subject: Mapped["Subject"] = relationship("Subject", back_populates="fields")
