"""
Presentation Definition and Request database models.
Based on DIF Presentation Exchange specification.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PresentationDefinition(Base):
    """
    DIF Presentation Definition model.
    Stores the complete presentation definition for verification requests.
    """
    
    __tablename__ = "presentation_definitions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    definition_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=True)
    subject_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    use_case: Mapped[str] = mapped_column(String(50), nullable=False, default="bank")
    account_type: Mapped[str] = mapped_column(String(50), nullable=False)
    requested_fields: Mapped[dict] = mapped_column(JSON, nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    qr_code_s3_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    qr_code_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    
    # Relationships
    subject: Mapped["Subject"] = relationship("Subject", lazy="selectin")
    requests: Mapped[List["PresentationRequest"]] = relationship(
        "PresentationRequest",
        back_populates="definition",
        cascade="all, delete-orphan",
    )


class PresentationRequest(Base):
    """
    Tracks presentation requests made against a definition.
    Records when users scan QR and submit credentials.
    """
    
    __tablename__ = "presentation_requests"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    definition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("presentation_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    holder_did: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    submission_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    definition: Mapped["PresentationDefinition"] = relationship(
        "PresentationDefinition",
        back_populates="requests",
    )


# Import for type hints
from app.models.subject import Subject
