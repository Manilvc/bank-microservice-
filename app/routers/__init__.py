"""API routers package."""

from app.routers.subjects import router as subjects_router
from app.routers.presentations import router as presentations_router
from app.routers.health import router as health_router

__all__ = [
    "subjects_router",
    "presentations_router",
    "health_router",
]
