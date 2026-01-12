"""
Application configuration module using pydantic-settings.
Loads environment variables and provides typed configuration.
"""

from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )
    
    # Application
    app_name: str = "Bank Wallet Microservice"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    # Database
    database_url: str = Field(..., description="Database connection URL (loaded from .env)")
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # AWS S3 - Support both new and old environment variable names
    aws_access_key: str = Field(
        ...,
        validation_alias=AliasChoices("AWS_ACCESS_KEY", "aws_access_key_id"),
        description="AWS access key (loaded from .env as AWS_ACCESS_KEY or aws_access_key_id)"
    )
    aws_secret_key: str = Field(
        ...,
        validation_alias=AliasChoices("AWS_SECRET_KEY", "aws_secret_access_key"),
        description="AWS secret key (loaded from .env as AWS_SECRET_KEY or aws_secret_access_key)"
    )
    aws_region: str = Field(
        default="ap-south-1",
        validation_alias=AliasChoices("AWS_REGION", "REGION", "aws_region"),
        description="AWS region"
    )
    public_bucket: str = Field(
        ...,
        validation_alias=AliasChoices("PUBLIC_BUCKET", "s3_bucket_name"),
        description="Public S3 bucket name (loaded from .env as PUBLIC_BUCKET or s3_bucket_name)"
    )
    private_bucket: Optional[str] = Field(
        default=None,
        validation_alias="private_bucket",
        description="Private S3 bucket name (loaded from .env)"
    )
    aws_base_url: Optional[str] = Field(
        default=None,
        validation_alias="AWS_BASE_URL",
        description="AWS base URL for S3"
    )
    proxy_base_url: Optional[str] = Field(
        default=None,
        validation_alias="PROXY_BASE_URL",
        description="Proxy base URL for S3 access"
    )
    aws_expire_time: int = Field(
        default=3600,
        validation_alias="AWS_EXPIRE_TIME",
        description="Default expiration time in seconds for presigned URLs"
    )
    support_lambda_function: bool = Field(
        default=False,
        validation_alias="support_lambda_function",
        description="Whether to support Lambda function integration"
    )
    
    # Backward compatibility properties
    @property
    def aws_access_key_id(self) -> str:
        """Alias for aws_access_key for backward compatibility."""
        return self.aws_access_key
    
    @property
    def aws_secret_access_key(self) -> str:
        """Alias for aws_secret_key for backward compatibility."""
        return self.aws_secret_key
    
    @property
    def s3_bucket_name(self) -> str:
        """Alias for public_bucket for backward compatibility."""
        return self.public_bucket
    
    @property
    def s3_endpoint_url(self) -> Optional[str]:
        """Alias for aws_base_url for backward compatibility."""
        return self.aws_base_url
    
    # DID Configuration
    did_method: str = "evrc"
    did_issuer_id: str = "bank-wallet-issuer"
    
    # Presentation Definition
    presentation_expiry_hours: int = 24
    qr_code_size: int = 300
    
    # CORS
    cors_origins: str = "*"
    
    # API Base URL
    api_base_url: Optional[str] = Field(
        default=None,
        validation_alias="API_BASE_URL",
        description="Base URL for API endpoints (e.g., https://api.example.com). If not set, will be constructed from server_host and server_port"
    )

    # Server
    server_host: str = Field(
        default="0.0.0.0",
        description="Server host (loaded from .env as SERVER_HOST or server_host)"
    )
    server_port: int = Field(
        default=8001,
        description="Server port (loaded from .env as SERVER_PORT or server_port)"
    )
    
    @property
    def api_url(self) -> str:
        """Get API base URL, constructing from host/port if not explicitly set."""
        if self.api_base_url:
            return self.api_base_url.rstrip('/')
        # Construct from host and port
        host = self.server_host if self.server_host != "0.0.0.0" else "localhost"
        return f"http://{host}:{self.server_port}"
    
    @property
    def host(self) -> str:
        """Alias for server_host for backward compatibility."""
        return self.server_host
    
    @property
    def port(self) -> int:
        """Alias for server_port for backward compatibility."""
        return self.server_port


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
