"""
Authentication API endpoints.
Handles user authentication and token validation.
"""

from fastapi import APIRouter, Depends, status, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import get_current_user, get_auth_service
from app.services.user_service import get_user_service, UserService
from app.schemas.auth import (
    UserContext,
    SignupRequest,
    SigninRequest,
    SignupResponse,
    SigninResponse,
)
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

security = HTTPBearer(auto_error=False)


@router.get(
    "/me",
    response_model=dict,
    summary="Get Current User",
    description="Get information about the currently authenticated user",
    responses={
        200: {"description": "User information retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
    },
)
async def get_current_user_info(
    user: UserContext = Depends(get_current_user),
) -> dict:
    """
    Get current authenticated user information.
    
    Returns user context including:
    - User ID
    - Email
    - Use case (bank, hotel, etc.)
    - Role
    - Department
    - Name
    - Organization ID
    """
    return {
        "success": True,
        "message": "User information retrieved successfully",
        "data": {
            "user_id": user.user_id,
            "email": user.email,
            "use_case": user.use_case,
            "role": user.role,
            "department": user.department,
            "name": user.name,
            "organization_id": user.organization_id,
        },
    }


@router.post(
    "/validate",
    response_model=dict,
    summary="Validate Token",
    description="Validate an authentication token and get user context",
    responses={
        200: {"description": "Token is valid"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def validate_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Validate an authentication token.
    
    This endpoint validates the provided Bearer token and returns
    the user context if the token is valid.
    
    Use this endpoint to verify tokens before making other API calls.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    auth_service = get_auth_service()
    user_context = await auth_service.validate_token_and_get_user(
        credentials=credentials,
    )
    
    return {
        "success": True,
        "message": "Token is valid",
        "data": {
            "user_id": user_context.user_id,
            "email": user_context.email,
            "use_case": user_context.use_case,
            "role": user_context.role,
            "department": user_context.department,
            "name": user_context.name,
            "organization_id": user_context.organization_id,
        },
    }


@router.post(
    "/signup",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="User Signup",
    description="Register a new user account for a specific use case",
    responses={
        201: {"description": "User registered successfully"},
        400: {"model": ErrorResponse, "description": "User already exists or validation error"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def signup(
    request: SignupRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Register a new user account.
    
    Creates a new user account for the specified use case (bank, hotel, etc.).
    The password will be securely hashed before storage.
    
    Returns user information without password.
    """
    user_service = get_user_service(db=db)
    
    # Create user
    user = user_service.create_user(
        email=request.email,
        password=request.password,
        use_case=request.use_case,
        name=request.name,
        role=request.role,
        department=request.department,
        organization_id=request.organization_id,
    )
    
    return {
        "success": True,
        "message": "User registered successfully",
        "data": {
            "user_id": user.user_id,
            "email": user.email,
            "use_case": user.use_case,
            "name": user.name,
            "role": user.role,
            "department": user.department,
            "organization_id": user.organization_id,
            "created_at": user.created_at.isoformat(),
        },
    }


@router.post(
    "/signin",
    response_model=dict,
    summary="User Signin",
    description="Authenticate user and get access token",
    responses={
        200: {"description": "Authentication successful"},
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "User account is inactive"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def signin(
    request: SigninRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Authenticate user and get access token.
    
    Validates user credentials and returns JWT access token and refresh token.
    The tokens can be used to authenticate subsequent API requests.
    
    Returns:
    - access_token: JWT access token
    - refresh_token: JWT refresh token (optional)
    - token_type: Token type (bearer)
    - expires_in: Token expiration time in seconds
    - user: User context information
    """
    user_service = get_user_service(db=db)
    
    # Authenticate user
    user = user_service.authenticate_user(
        email=request.email,
        password=request.password,
        use_case=request.use_case,
    )
    
    # Generate tokens
    access_token = user_service.create_access_token(user=user)
    refresh_token = user_service.create_refresh_token(user=user)
    
    # Get client info
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")
    
    # Create session
    session = user_service.create_user_session(
        user=user,
        access_token=access_token,
        refresh_token=refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    # Create user context
    user_context = UserContext(
        user_id=user.user_id,
        email=user.email,
        use_case=user.use_case,
        role=user.role,
        department=user.department,
        name=user.name,
        organization_id=user.organization_id,
    )
    
    from app.config import get_settings
    settings = get_settings()
    expires_in = settings.jwt_access_token_expire_minutes * 60
    
    return {
        "success": True,
        "message": "Authentication successful",
        "data": {
            "session_id": session.id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "user": user_context.model_dump(),
        },
    }


@router.get(
    "/session/{session_id}",
    response_model=dict,
    summary="Get User by Session ID",
    description="Retrieve user information using session ID",
    responses={
        200: {"description": "User information retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Session expired or invalid"},
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
)
def get_user_by_session_id(
    session_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Get user information by session ID.
    
    Retrieves user data associated with the given session ID.
    The session must be active and not expired.
    
    Args:
        session_id: Session database ID
        
    Returns:
        User information and session details
    """
    user_service = get_user_service(db=db)
    
    # Get user from session
    user = user_service.get_user_from_session_id(session_id=session_id)
    session = user_service.get_session_by_id(session_id=session_id)
    
    # Create user context
    user_context = UserContext(
        user_id=user.user_id,
        email=user.email,
        use_case=user.use_case,
        role=user.role,
        department=user.department,
        name=user.name,
        organization_id=user.organization_id,
    )
    
    return {
        "success": True,
        "message": "User information retrieved successfully",
        "data": {
            "session_id": session.id,
            "user": user_context.model_dump(),
            "session": {
                "is_active": session.is_active,
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                "created_at": session.created_at.isoformat(),
                "last_activity_at": session.last_activity_at.isoformat(),
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
            },
        },
    }


@router.get(
    "/health",
    response_model=dict,
    summary="Auth Service Health",
    description="Check authentication service health and configuration",
    responses={
        200: {"description": "Auth service health status"},
    },
)
async def auth_health() -> dict:
    """
    Check authentication service health.
    
    Returns information about:
    - Auth API URL configuration
    - Token validation status
    - Service availability
    """
    from app.config import get_settings
    
    settings = get_settings()
    auth_api_url = getattr(settings, "auth_api_url", None)
    validate_token = getattr(settings, "validate_token", True)
    
    return {
        "success": True,
        "message": "Auth service health check",
        "data": {
            "auth_api_configured": auth_api_url is not None,
            "auth_api_url": auth_api_url if auth_api_url else None,
            "token_validation_enabled": validate_token,
            "status": "healthy",
        },
    }
