"""
Authentication service for validating user tokens and extracting user context.
"""

import logging
from typing import Optional

import httpx
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas.auth import UserContext, AuthTokenResponse
from app.database import get_db
from app.models.auth import User

logger = logging.getLogger(__name__)
settings = get_settings()

security = HTTPBearer(auto_error=False)


class AuthService:
    """
    Service for handling authentication and user context extraction.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize auth service with configuration."""
        self.auth_api_url = getattr(settings, "auth_api_url", None)
        self.auth_api_timeout = getattr(settings, "auth_api_timeout", 5.0)
        self.validate_token = getattr(settings, "validate_token", True)
        self.db = db
        self.jwt_secret_key = settings.jwt_secret_key
        self.jwt_algorithm = settings.jwt_algorithm
    
    async def validate_token_and_get_user(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = None,
    ) -> UserContext:
        """
        Validate authentication token and extract user context.
        
        Args:
            credentials: HTTP Bearer token credentials
            
        Returns:
            UserContext with user information and use_case
            
        Raises:
            HTTPException: If token is invalid or missing
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = credentials.credentials
        
        # Try to validate JWT token locally first
        try:
            user_context = self._validate_jwt_token(token=token)
            return user_context
        except HTTPException:
            # If JWT validation fails, try external API if configured
            pass
        
        # If auth API is configured, validate token via external API
        if self.auth_api_url and self.validate_token:
            try:
                user_context = await self._validate_via_api(token=token)
                return user_context
            except Exception as e:
                logger.error(f"Token validation failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                )
        
        # Fallback: Extract from token directly (for development/testing)
        # In production, always use external auth API
        logger.warning("Using fallback token validation - not recommended for production")
        return self._extract_from_token_fallback(token=token)
    
    def _validate_jwt_token(self, token: str) -> UserContext:
        """
        Validate JWT token locally.
        
        Args:
            token: JWT token string
            
        Returns:
            UserContext extracted from token
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret_key,
                algorithms=[self.jwt_algorithm],
            )
            
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user identifier",
                )
            
            # Optionally verify user exists in database
            if self.db:
                user = self.db.query(User).filter(User.user_id == user_id).first()
                if not user or not user.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found or inactive",
                    )
            
            return UserContext(
                user_id=user_id,
                email=payload.get("email"),
                use_case=payload.get("use_case", "bank").lower(),
                role=payload.get("role"),
                department=payload.get("department"),
                name=payload.get("name"),
                organization_id=payload.get("organization_id"),
            )
            
        except JWTError as e:
            logger.error(f"JWT validation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
    
    async def _validate_via_api(self, token: str) -> UserContext:
        """
        Validate token via external authentication API.
        
        Args:
            token: JWT or bearer token
            
        Returns:
            UserContext extracted from API response
        """
        if not self.auth_api_url:
            raise ValueError("Auth API URL not configured")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=self.auth_api_timeout) as client:
            try:
                response = await client.get(
                    f"{self.auth_api_url.rstrip('/')}/validate",
                    headers=headers,
                )
                response.raise_for_status()
                
                data = response.json()
                auth_response = AuthTokenResponse(**data)
                
                return UserContext(
                    user_id=auth_response.user_id,
                    email=auth_response.email,
                    use_case=auth_response.use_case.lower(),  # Normalize to lowercase
                    role=auth_response.role,
                    department=auth_response.department,
                    name=auth_response.name,
                    organization_id=auth_response.organization_id,
                )
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Auth API returned error: {e.response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token validation failed",
                )
            except httpx.RequestError as e:
                logger.error(f"Auth API request failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service unavailable",
                )
    
    def _extract_from_token_fallback(self, token: str) -> UserContext:
        """
        Fallback method to extract user context from token.
        Only for development/testing. Not secure for production.
        
        Args:
            token: Bearer token (may contain user info in development)
            
        Returns:
            UserContext extracted from token
        """
        # For development: token might be in format "use_case:user_id:role"
        # In production, this should never be used
        parts = token.split(":", 2)
        
        if len(parts) >= 2:
            use_case = parts[0].lower()
            user_id = parts[1]
            role = parts[2] if len(parts) > 2 else None
            
            return UserContext(
                user_id=user_id,
                use_case=use_case,
                role=role,
            )
        
        # Default fallback
        return UserContext(
            user_id="dev_user",
            use_case="bank",  # Default use case
        )


# Global auth service instance
_auth_service: Optional[AuthService] = None


def get_auth_service(db: Optional[Session] = None) -> AuthService:
    """Get or create auth service instance."""
    return AuthService(db=db)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> UserContext:
    """
    FastAPI dependency to get current authenticated user.
    
    Usage:
        @router.get("/endpoint")
        async def my_endpoint(user: UserContext = Depends(get_current_user)):
            use_case = user.use_case
            ...
    """
    # Check if user context is already in request state (set by middleware)
    if hasattr(request.state, "user_context"):
        return request.state.user_context
    
    # Otherwise, validate token
    auth_service = get_auth_service(db=db)
    user_context = await auth_service.validate_token_and_get_user(
        credentials=credentials,
    )
    
    # Store in request state for reuse
    request.state.user_context = user_context
    
    return user_context
