"""
User service for registration, authentication, and user management.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import get_settings
from app.models.auth import User, UserSession
from app.schemas.auth import UserContext
from app.exceptions.custom_exceptions import DatabaseException, NotFoundException

logger = logging.getLogger(__name__)
settings = get_settings()

# Password hashing context - using pbkdf2_sha256 to avoid bcrypt initialization issues
# pbkdf2_sha256 doesn't have the 72-byte limit and doesn't trigger bcrypt backend detection
try:
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
except Exception as e:
    logger.error(f"Failed to initialize password context: {e}")
    raise


def hash_password(password: str) -> str:
    """
    Hash password using pbkdf2_sha256 (no length limit issues).
    """
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify password against hash.
    """
    return pwd_context.verify(password, password_hash)

# JWT settings
JWT_SECRET_KEY = settings.jwt_secret_key
JWT_ALGORITHM = settings.jwt_algorithm
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_access_token_expire_minutes
JWT_REFRESH_TOKEN_EXPIRE_DAYS = settings.jwt_refresh_token_expire_days


class UserService:
    """
    Service for user registration, authentication, and management.
    """
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
    
    def create_user(
        self,
        email: str,
        password: str,
        use_case: str,
        name: Optional[str] = None,
        role: Optional[str] = None,
        department: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> User:
        """
        Create a new user account.
        
        Args:
            email: User email address
            password: Plain text password (will be hashed)
            use_case: Use case identifier (bank, hotel, etc.)
            name: User display name
            role: User role
            department: User department
            organization_id: Organization identifier
            
        Returns:
            Created User model
            
        Raises:
            DatabaseException: If user creation fails
            HTTPException: If user already exists
        """
        # Check if user with email already exists for this use_case
        existing_user = (
            self.db.query(User)
            .filter(
                User.email == email.lower(),
                User.use_case == use_case.lower(),
            )
            .first()
        )
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email {email} already exists for use case {use_case}",
            )
        
        # Generate user_id (using email prefix + use_case)
        user_id = f"{email.split('@')[0]}_{use_case.lower()}"
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create user
        user = User(
            user_id=user_id,
            email=email.lower(),
            password_hash=password_hash,
            use_case=use_case.lower(),
            name=name,
            role=role,
            department=department,
            organization_id=organization_id,
            is_active=True,
        )
        
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            logger.info(f"Created user: {user_id} for use case: {use_case}")
            return user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create user: {str(e)}")
            raise DatabaseException(
                message=f"Failed to create user: {str(e)}",
            )
    
    def authenticate_user(
        self,
        email: str,
        password: str,
        use_case: Optional[str] = None,
    ) -> User:
        """
        Authenticate user with email and password.
        
        Args:
            email: User email address
            password: Plain text password
            use_case: Optional use case for validation
            
        Returns:
            Authenticated User model
            
        Raises:
            HTTPException: If authentication fails
        """
        # Find user by email
        query = self.db.query(User).filter(User.email == email.lower())
        
        if use_case:
            query = query.filter(User.use_case == use_case.lower())
        
        user = query.first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        # Verify password
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        
        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        try:
            self.db.commit()
            self.db.refresh(user)
        except Exception as e:
            logger.warning(f"Failed to update last_login_at: {str(e)}")
        
        return user
    
    def create_access_token(
        self,
        user: User,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create JWT access token for user.
        
        Args:
            user: User model
            expires_delta: Optional expiration time delta
            
        Returns:
            JWT token string
        """
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode = {
            "sub": user.user_id,
            "email": user.email,
            "use_case": user.use_case,
            "role": user.role,
            "department": user.department,
            "name": user.name,
            "organization_id": user.organization_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
        
        return encoded_jwt
    
    def create_refresh_token(
        self,
        user: User,
    ) -> str:
        """
        Create JWT refresh token for user.
        
        Args:
            user: User model
            
        Returns:
            JWT refresh token string
        """
        expire = datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode = {
            "sub": user.user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
        
        return encoded_jwt
    
    def create_user_session(
        self,
        user: User,
        access_token: str,
        refresh_token: Optional[str] = None,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        """
        Create user session record.
        
        Args:
            user: User model
            access_token: Access token string
            refresh_token: Optional refresh token string
            device_info: Device information
            ip_address: IP address
            user_agent: User agent string
            
        Returns:
            Created UserSession model
        """
        import hashlib
        
        # Hash tokens for storage
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()
        refresh_token_hash = (
            hashlib.sha256(refresh_token.encode()).hexdigest()
            if refresh_token
            else None
        )
        
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        
        session = UserSession(
            user_id=user.user_id,
            token_hash=token_hash,
            refresh_token_hash=refresh_token_hash,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            expires_at=expires_at,
        )
        
        try:
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            logger.info(f"Created session for user: {user.user_id}")
            return session
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create session: {str(e)}")
            raise DatabaseException(
                message=f"Failed to create session: {str(e)}",
            )
    
    def get_user_by_id(
        self,
        user_id: str,
        use_case: Optional[str] = None,
    ) -> User:
        """
        Get user by user_id.
        
        Args:
            user_id: User identifier
            use_case: Optional use case for validation
            
        Returns:
            User model
            
        Raises:
            NotFoundException: If user not found
        """
        query = self.db.query(User).filter(User.user_id == user_id)
        
        if use_case:
            query = query.filter(User.use_case == use_case.lower())
        
        user = query.first()
        
        if not user:
            raise NotFoundException(
                resource="User",
                identifier=user_id,
            )
        
        return user
    
    def get_user_by_email(
        self,
        email: str,
        use_case: Optional[str] = None,
    ) -> Optional[User]:
        """
        Get user by email.
        
        Args:
            email: User email
            use_case: Optional use case for filtering
            
        Returns:
            User model or None
        """
        query = self.db.query(User).filter(User.email == email.lower())
        
        if use_case:
            query = query.filter(User.use_case == use_case.lower())
        
        return query.first()
    
    def get_session_by_id(
        self,
        session_id: int,
    ) -> UserSession:
        """
        Get session by session ID.
        
        Args:
            session_id: Session database ID
            
        Returns:
            UserSession model
            
        Raises:
            NotFoundException: If session not found
        """
        session = (
            self.db.query(UserSession)
            .filter(
                UserSession.id == session_id,
                UserSession.is_active == True,
            )
            .first()
        )
        
        if not session:
            raise NotFoundException(
                resource="Session",
                identifier=str(session_id),
            )
        
        # Check if session is expired
        if session.expires_at and session.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has expired",
            )
        
        return session
    
    def get_user_from_session_id(
        self,
        session_id: int,
    ) -> User:
        """
        Get user from session ID.
        
        Args:
            session_id: Session database ID
            
        Returns:
            User model
            
        Raises:
            NotFoundException: If session or user not found
            HTTPException: If session is expired or inactive
        """
        session = self.get_session_by_id(session_id=session_id)
        
        user = self.get_user_by_id(user_id=session.user_id)
        
        return user


def get_user_service(db: Session) -> UserService:
    """Factory function for UserService."""
    return UserService(db=db)
