"""
Health check endpoints.
Used for service monitoring and load balancer checks.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.config import get_settings

router = APIRouter(prefix="/health", tags=["Health"])
settings = get_settings()


class HealthResponse(BaseModel):
    """Health check response schema."""
    
    status: str = Field(description="Service status")
    service: str = Field(description="Service name")
    version: str = Field(description="Service version")
    timestamp: datetime = Field(description="Check timestamp")
    database: str = Field(description="Database connection status")


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check service health and database connectivity",
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Perform health check.
    
    Verifies:
    - Service is running
    - Database is accessible
    """
    # Check database
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
    
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.utcnow(),
        database=db_status,
    )


@router.get(
    "/ready",
    summary="Readiness Check",
    description="Check if service is ready to accept traffic",
)
def readiness_check(db: Session = Depends(get_db)) -> dict:
    """Check if service is ready."""
    try:
        db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        return {"ready": False}


@router.get(
    "/live",
    summary="Liveness Check",
    description="Check if service is alive",
)
def liveness_check() -> dict:
    """Check if service is alive."""
    return {"alive": True}
