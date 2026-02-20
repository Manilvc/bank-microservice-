"""
Authentication and user context schemas.
"""

from typing import Optional
from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """
    User context extracted from authentication token.
    Contains user identity and use case information.
    """
    
    user_id: str = Field(description="Unique user identifier")
    email: Optional[str] = Field(default=None, description="User email address")
    use_case: str = Field(description="Use case identifier (bank, hotel, etc.)")
    role: Optional[str] = Field(default=None, description="User role (e.g., Manager, Admin)")
    department: Optional[str] = Field(default=None, description="User department")
    name: Optional[str] = Field(default=None, description="User display name")
    organization_id: Optional[str] = Field(default=None, description="Organization identifier")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "email": "user@example.com",
                "use_case": "hotel",
                "role": "Hotel Manager",
                "department": "Front Desk",
                "name": "John Doe",
                "organization_id": "org_456",
            }
        }


class AuthTokenResponse(BaseModel):
    """
    Response from authentication API.
    """
    
    user_id: str
    email: Optional[str] = None
    use_case: str
    role: Optional[str] = None
    department: Optional[str] = None
    name: Optional[str] = None
    organization_id: Optional[str] = None
    permissions: Optional[list[str]] = None


class SignupRequest(BaseModel):
    """
    User registration request schema.
    """
    
    email: str = Field(description="User email address")
    password: str = Field(min_length=8, description="User password (minimum 8 characters)")
    use_case: str = Field(description="Use case identifier (bank, hotel, etc.)")
    name: Optional[str] = Field(default=None, description="User display name")
    role: Optional[str] = Field(default=None, description="User role")
    department: Optional[str] = Field(default=None, description="User department")
    organization_id: Optional[str] = Field(default=None, description="Organization identifier")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
                "use_case": "hotel",
                "name": "John Doe",
                "role": "Hotel Manager",
                "department": "Front Desk",
                "organization_id": "org_456",
            }
        }


class SigninRequest(BaseModel):
    """
    User signin request schema.
    """
    
    email: str = Field(description="User email address")
    password: str = Field(description="User password")
    use_case: Optional[str] = Field(default=None, description="Use case identifier (optional, for validation)")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
                "use_case": "hotel",
            }
        }


class SignupResponse(BaseModel):
    """
    User registration response schema.
    """
    
    user_id: str
    email: str
    use_case: str
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    organization_id: Optional[str] = None
    created_at: str


class SigninResponse(BaseModel):
    """
    User signin response schema with tokens.
    """
    
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: UserContext
