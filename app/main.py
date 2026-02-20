"""
Bank Wallet Microservice - FastAPI Application Entry Point.

This application provides APIs for:
- Managing KYC document types (subjects) and their fields
- Creating DIF Presentation Definitions for verification
- Generating QR codes for wallet interactions
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import (
    subjects_router,
    presentations_router,
    health_router,
    submissions_router,
    dashboard_router,
    auth_router,
)
from app.exceptions import register_exception_handlers
from app.middleware import RequestIDMiddleware, LoggingMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for startup and shutdown events.
    Replaces deprecated on_event decorators.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


def create_app() -> FastAPI:
    """
    Application factory function.
    Creates and configures the FastAPI application.
    """
    app = FastAPI(
        lifespan=lifespan,
        title=settings.app_name,
        version=settings.app_version,
        description="""
## Bank Wallet Microservice API

This API provides endpoints for KYC verification using Verifiable Credentials.

### Features:
- **Subjects**: Manage KYC document types (Aadhar, PAN, Voter ID)
- **Fields**: Define extractable fields for each document type
- **Presentations**: Create DIF-compliant presentation definitions
- **QR Codes**: Generate QR codes for wallet scanning

### Error Handling:
All errors return a standard response format with:
- `success`: Always `false` for errors
- `error`: Error type/code
- `message`: Human-readable description
- `status_code`: HTTP status code
- `details`: Detailed error information (for validation errors)
- `request_id`: Request tracking ID
- `timestamp`: Error occurrence time
- `path`: Request path
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)
    
    # Register exception handlers
    register_exception_handlers(app=app)
    
    # Include routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(subjects_router, prefix="/api/v1")
    app.include_router(presentations_router, prefix="/api/v1")
    app.include_router(submissions_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "docs": "/docs",
            "health": "/api/v1/health",
        }
    
    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
