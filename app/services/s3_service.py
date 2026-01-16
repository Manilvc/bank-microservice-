"""
AWS S3 service for file storage operations.
Handles QR code image uploads and URL generation.
"""

import io
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings
from app.exceptions.custom_exceptions import S3Exception

logger = logging.getLogger(__name__)
settings = get_settings()


class S3Service:
    """Service for S3 file operations."""
    
    def __init__(self):
        """Initialize S3 client with configuration."""
        self._client = None
    
    @property
    def client(self):
        """Lazy-load S3 client."""
        if self._client is None:
            config = {
                "aws_access_key_id": settings.aws_access_key,
                "aws_secret_access_key": settings.aws_secret_key,
                "region_name": settings.aws_region,
            }
            if settings.aws_base_url:
                config["endpoint_url"] = settings.aws_base_url
            
            self._client = boto3.client("s3", **config)
        return self._client
    
    def upload_image(
        self,
        image_bytes: bytes,
        s3_key: str,
        content_type: str = "image/png",
    ) -> str:
        """
        Upload image bytes to S3.
        
        Args:
            image_bytes: Image data as bytes
            s3_key: S3 object key (path)
            content_type: MIME type of the image
            
        Returns:
            S3 object URL
            
        Raises:
            S3Exception: If upload fails
        """
        try:
            # Build upload parameters
            upload_params = {
                "Bucket": settings.public_bucket,
                "Key": s3_key,
                "Body": io.BytesIO(image_bytes),
                "ContentType": content_type,
            }
            
            # Only set ACL if using standard AWS S3 (custom endpoints like MinIO don't support ACL)
            if not settings.aws_base_url:
                upload_params["ACL"] = "public-read"
            
            self.client.put_object(**upload_params)
            
            # Try to make object public if using standard AWS S3 (for proxy/CDN access)
            # This helps when proxy needs to access the file
            if not settings.aws_base_url and settings.proxy_base_url:
                try:
                    self.client.put_object_acl(
                        Bucket=settings.public_bucket,
                        Key=s3_key,
                        ACL="public-read",
                    )
                    logger.info(f"Set public-read ACL for {s3_key}")
                except ClientError as acl_error:
                    acl_error_code = acl_error.response.get("Error", {}).get("Code", "Unknown")
                    logger.warning(f"Could not set ACL for {s3_key}: {acl_error_code}")
            
            # Verify upload by checking if object exists
            try:
                self.client.head_object(Bucket=settings.public_bucket, Key=s3_key)
                logger.info(f"Verified upload: {s3_key} exists in bucket {settings.public_bucket}")
            except ClientError as verify_error:
                logger.warning(f"Could not verify upload for {s3_key}: {str(verify_error)}")
            
            # Generate accessible URL
            # Prefer proxy URL if available (permanent, clean URL matching working format)
            # Fallback to presigned URL if no proxy configured
            if settings.proxy_base_url:
                url = self._generate_url(s3_key=s3_key)
                presigned_url = self.get_presigned_url(s3_key=s3_key, expiry_seconds=settings.aws_expire_time)
                direct_url = self.get_direct_s3_url(s3_key=s3_key)
                logger.info(
                    f"Uploaded image to S3: {s3_key} -> Proxy URL (primary): {url}, "
                    f"Presigned URL (fallback): {presigned_url}, Direct S3 URL: {direct_url}"
                )
            else:
                # No proxy configured, use presigned URL for guaranteed access
                url = self.get_presigned_url(s3_key=s3_key, expiry_seconds=settings.aws_expire_time)
                direct_url = self.get_direct_s3_url(s3_key=s3_key)
                logger.info(
                    f"Uploaded image to S3: {s3_key} -> Presigned URL: {url}, Direct S3 URL: {direct_url}"
                )
            
            return url
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            
            # If ACL is not supported, retry without ACL
            if error_code == "AccessControlListNotSupported":
                try:
                    logger.warning(f"ACL not supported, retrying upload without ACL for {s3_key}")
                    self.client.put_object(
                        Bucket=settings.public_bucket,
                        Key=s3_key,
                        Body=io.BytesIO(image_bytes),
                        ContentType=content_type,
                    )
                    
                    # Try to make object public if using standard AWS S3 (for proxy/CDN access)
                    if not settings.aws_base_url and settings.proxy_base_url:
                        try:
                            self.client.put_object_acl(
                                Bucket=settings.public_bucket,
                                Key=s3_key,
                                ACL="public-read",
                            )
                            logger.info(f"Set public-read ACL for {s3_key} (retry)")
                        except ClientError as acl_error:
                            acl_error_code = acl_error.response.get("Error", {}).get("Code", "Unknown")
                            logger.warning(f"Could not set ACL for {s3_key}: {acl_error_code}")
                    
                    # Verify upload
                    try:
                        self.client.head_object(Bucket=settings.public_bucket, Key=s3_key)
                        logger.info(f"Verified upload (without ACL): {s3_key} exists")
                    except ClientError as verify_error:
                        logger.warning(f"Could not verify upload for {s3_key}: {str(verify_error)}")
                    
                    # Generate URL - prefer proxy if available
                    if settings.proxy_base_url:
                        url = self._generate_url(s3_key=s3_key)
                        presigned_url = self.get_presigned_url(s3_key=s3_key, expiry_seconds=settings.aws_expire_time)
                        direct_url = self.get_direct_s3_url(s3_key=s3_key)
                        logger.info(
                            f"Uploaded image to S3 (without ACL): {s3_key} -> Proxy URL (primary): {url}, "
                            f"Presigned URL (fallback): {presigned_url}, Direct S3 URL: {direct_url}"
                        )
                    else:
                        url = self.get_presigned_url(s3_key=s3_key, expiry_seconds=settings.aws_expire_time)
                        direct_url = self.get_direct_s3_url(s3_key=s3_key)
                        logger.info(
                            f"Uploaded image to S3 (without ACL): {s3_key} -> Presigned URL: {url}, Direct S3 URL: {direct_url}"
                        )
                    
                    return url
                except ClientError as retry_error:
                    retry_code = retry_error.response.get("Error", {}).get("Code", "Unknown")
                    logger.error(f"S3 upload failed (retry): {retry_code} - {str(retry_error)}")
                    raise S3Exception(
                        message=f"Failed to upload image: {retry_code}",
                        operation="upload",
                    )
            
            logger.error(f"S3 upload failed: {error_code} - {str(e)}")
            raise S3Exception(
                message=f"Failed to upload image: {error_code}",
                operation="upload",
            )
    
    def upload_json(
        self,
        json_data: dict | str,
        s3_key: str,
        content_type: str = "application/json",
    ) -> str:
        """
        Upload JSON data to S3.
        
        Args:
            json_data: JSON data as dict or JSON string
            s3_key: S3 object key (path)
            content_type: MIME type (default: application/json)
            
        Returns:
            S3 object URL
            
        Raises:
            S3Exception: If upload fails
        """
        import json as json_lib
        
        try:
            # Convert dict to JSON string if needed
            if isinstance(json_data, dict):
                content = json_lib.dumps(json_data, separators=(",", ":"), ensure_ascii=False)
            else:
                content = str(json_data)
            
            # Convert string to bytes
            content_bytes = content.encode('utf-8')
            
            # Build upload parameters
            upload_params = {
                "Bucket": settings.public_bucket,
                "Key": s3_key,
                "Body": content_bytes,
                "ContentType": content_type,
            }
            
            # Only set ACL if using standard AWS S3 (custom endpoints like MinIO don't support ACL)
            if not settings.aws_base_url:
                upload_params["ACL"] = "public-read"
            
            self.client.put_object(**upload_params)
            
            # Try to make object public if using standard AWS S3
            if not settings.aws_base_url and settings.proxy_base_url:
                try:
                    self.client.put_object_acl(
                        Bucket=settings.public_bucket,
                        Key=s3_key,
                        ACL="public-read",
                    )
                    logger.info(f"Set public-read ACL for {s3_key}")
                except ClientError as acl_error:
                    acl_error_code = acl_error.response.get("Error", {}).get("Code", "Unknown")
                    logger.warning(f"Could not set ACL for {s3_key}: {acl_error_code}")
            
            # Verify upload
            try:
                self.client.head_object(Bucket=settings.public_bucket, Key=s3_key)
                logger.info(f"Verified upload: {s3_key} exists in bucket {settings.public_bucket}")
            except ClientError as verify_error:
                logger.warning(f"Could not verify upload for {s3_key}: {str(verify_error)}")
            
            # Generate accessible URL
            if settings.proxy_base_url:
                url = self._generate_url(s3_key=s3_key)
                logger.info(f"Uploaded JSON to S3: {s3_key} -> Proxy URL: {url}")
            else:
                url = self.get_presigned_url(s3_key=s3_key, expiry_seconds=settings.aws_expire_time)
                logger.info(f"Uploaded JSON to S3: {s3_key} -> Presigned URL: {url}")
            
            return url
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            
            # If ACL is not supported, retry without ACL
            if error_code == "AccessControlListNotSupported":
                try:
                    logger.warning(f"ACL not supported, retrying upload without ACL for {s3_key}")
                    self.client.put_object(
                        Bucket=settings.public_bucket,
                        Key=s3_key,
                        Body=content_bytes,
                        ContentType=content_type,
                    )
                    
                    # Generate URL
                    if settings.proxy_base_url:
                        url = self._generate_url(s3_key=s3_key)
                    else:
                        url = self.get_presigned_url(s3_key=s3_key, expiry_seconds=settings.aws_expire_time)
                    
                    logger.info(f"Uploaded JSON to S3 (without ACL): {s3_key} -> {url}")
                    return url
                except ClientError as retry_error:
                    retry_code = retry_error.response.get("Error", {}).get("Code", "Unknown")
                    logger.error(f"S3 JSON upload failed (retry): {retry_code} - {str(retry_error)}")
                    raise S3Exception(
                        message=f"Failed to upload JSON: {retry_code}",
                        operation="upload_json",
                    )
            
            logger.error(f"S3 JSON upload failed: {error_code} - {str(e)}")
            raise S3Exception(
                message=f"Failed to upload JSON: {error_code}",
                operation="upload_json",
            )
    
    def delete_object(self, s3_key: str) -> bool:
        """
        Delete object from S3.
        
        Args:
            s3_key: S3 object key to delete
            
        Returns:
            True if deletion successful
            
        Raises:
            S3Exception: If deletion fails
        """
        try:
            self.client.delete_object(
                Bucket=settings.public_bucket,
                Key=s3_key,
            )
            logger.info(f"Deleted S3 object: {s3_key}")
            return True
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 delete failed: {error_code}")
            raise S3Exception(
                message=f"Failed to delete object: {error_code}",
                operation="delete",
            )
    
    def get_presigned_url(
        self,
        s3_key: str,
        expiry_seconds: Optional[int] = None,
    ) -> str:
        """
        Generate presigned URL for private objects.
        
        Args:
            s3_key: S3 object key
            expiry_seconds: URL expiration in seconds
            
        Returns:
            Presigned URL string
        """
        try:
            expiry = expiry_seconds or settings.aws_expire_time
            url = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": settings.public_bucket,
                    "Key": s3_key,
                },
                ExpiresIn=expiry,
            )
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise S3Exception(
                message="Failed to generate presigned URL",
                operation="presign",
            )
    
    def _generate_url(self, s3_key: str) -> str:
        """
        Generate public URL for S3 object.
        
        Args:
            s3_key: S3 object key (path)
            
        Returns:
            Public URL string
        """
        # Use proxy base URL if available (for CDN or proxy)
        # Proxy URL format: {proxy_base_url}/{bucket_name}/{s3_key}
        if settings.proxy_base_url:
            base_url = settings.proxy_base_url.rstrip('/')
            key_path = s3_key.lstrip('/')
            url = f"{base_url}/{settings.public_bucket}/{key_path}"
            logger.debug(f"Generated proxy URL: {url}")
            return url
        
        # Use AWS base URL if available (for custom endpoints like MinIO)
        if settings.aws_base_url:
            base_url = settings.aws_base_url.rstrip('/')
            key_path = s3_key.lstrip('/')
            url = f"{base_url}/{settings.public_bucket}/{key_path}"
            logger.debug(f"Generated AWS base URL: {url}")
            return url
        
        # Default AWS S3 URL format
        key_path = s3_key.lstrip('/')
        url = f"https://{settings.public_bucket}.s3.{settings.aws_region}.amazonaws.com/{key_path}"
        logger.debug(f"Generated default S3 URL: {url}")
        return url
    
    def object_exists(self, s3_key: str) -> bool:
        """
        Check if an object exists in S3.
        
        Args:
            s3_key: S3 object key to check
            
        Returns:
            True if object exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=settings.public_bucket, Key=s3_key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                return False
            logger.warning(f"Error checking object existence: {error_code}")
            return False
    
    def get_direct_s3_url(self, s3_key: str) -> str:
        """
        Get direct S3 URL (bypassing proxy/CDN).
        Useful for verification or fallback.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Direct S3 URL string
        """
        if settings.aws_base_url:
            base_url = settings.aws_base_url.rstrip('/')
            key_path = s3_key.lstrip('/')
            return f"{base_url}/{settings.public_bucket}/{key_path}"
        
        key_path = s3_key.lstrip('/')
        return f"https://{settings.public_bucket}.s3.{settings.aws_region}.amazonaws.com/{key_path}"
    
    def get_accessible_url(self, s3_key: str, prefer_presigned: bool = False) -> str:
        """
        Get an accessible URL for the S3 object.
        Tries multiple strategies to ensure the URL works.
        
        Args:
            s3_key: S3 object key
            prefer_presigned: If True, prefer presigned URL over proxy URL
            
        Returns:
            Accessible URL string
        """
        # If presigned is preferred or no proxy, use presigned URL
        if prefer_presigned or not settings.proxy_base_url:
            return self.get_presigned_url(s3_key=s3_key, expiry_seconds=settings.aws_expire_time)
        
        # Otherwise, use proxy URL (presigned available as fallback)
        return self._generate_url(s3_key=s3_key)


def get_s3_service() -> S3Service:
    """Dependency for S3 service."""
    return S3Service()
