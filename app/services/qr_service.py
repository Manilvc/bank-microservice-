"""
QR Code generation service.
Creates QR codes for presentation definitions.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any

import qrcode
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_M
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class QRCodeService:
    """Service for generating QR codes."""
    
    def __init__(
        self,
        size: int | None = None,
        border: int = 4,
        error_correction: int = ERROR_CORRECT_H,
    ):
        """
        Initialize QR code service.
        
        Args:
            size: QR code size in pixels
            border: Border size in modules
            error_correction: Error correction level (default: HIGH for better reliability)
        """
        self.size = size or settings.qr_code_size
        self.border = border
        self.error_correction = error_correction
    
    def generate_qr_bytes(
        self,
        data: dict[str, Any] | str,
        format: str = "PNG",
    ) -> bytes:
        """
        Generate QR code as bytes.
        
        Args:
            data: Data to encode (dict will be JSON serialized)
            format: Image format (PNG, JPEG)
            
        Returns:
            Image bytes
        """
        # Convert dict to JSON string
        if isinstance(data, dict):
            content = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        else:
            content = str(data)
        
        content_length = len(content)
        logger.info(f"Generating QR code for data length: {content_length} characters")
        
        # Check if data is too large for QR code (max ~2953 bytes for version 40 with H error correction)
        # Using a safer limit of 2500 to ensure scannability
        max_chars = 2500
        if content_length > max_chars:
            logger.warning(
                f"QR code data ({content_length} chars) exceeds safe size ({max_chars} chars). "
                f"Will attempt to generate, but may fail or be difficult to scan."
            )
        
        # Adjust box_size based on data size for better scannability
        # Larger data needs smaller box_size to fit, but we want it scannable
        if content_length > 1000:
            box_size = 8  # Smaller boxes for large data
        elif content_length > 500:
            box_size = 9
        else:
            box_size = 10
        
        # Create QR code with high error correction for better reliability
        qr = qrcode.QRCode(
            version=None,  # Auto-determine version based on data size
            error_correction=self.error_correction,
            box_size=box_size,
            border=self.border,
        )
        
        try:
            qr.add_data(content)
            qr.make(fit=True)
            
            # Check if version exceeds maximum (40) - this should not happen after make(),
            # but check anyway for safety
            if hasattr(qr, 'version') and qr.version and qr.version > 40:
                raise ValueError(
                    f"QR code data too large: requires version {qr.version} (max is 40). "
                    f"Data length: {content_length} characters. "
                    f"Please use URL-based approach for large data."
                )
            
            # Get QR code version for logging
            qr_version = qr.version if hasattr(qr, 'version') else "auto"
            logger.info(
                f"QR code generated: version={qr_version}, box_size={box_size}, "
                f"final_size={self.size}px, error_correction=HIGH, data_length={content_length}"
            )
            
        except ValueError as ve:
            error_str = str(ve).lower()
            # Check for version-related errors (e.g., "Invalid version (was 41, expected 1 to 40)")
            if "version" in error_str and ("41" in error_str or "40" in error_str or "invalid" in error_str):
                logger.error(f"QR code data too large: {str(ve)}")
                raise ValueError(
                    f"QR code data is too large ({content_length} characters). "
                    f"QR code version exceeds maximum (40). Please use URL-based approach for large data."
                ) from ve
            # Check for data overflow or too large errors
            if "too large" in error_str or "overflow" in error_str:
                logger.error(f"QR code data too large ({content_length} chars). Maximum is ~2953 chars.")
                raise ValueError(
                    f"QR code data is too large ({content_length} characters). "
                    f"Maximum recommended size is 2953 characters. Please use URL-based approach."
                ) from ve
            # Re-raise other ValueErrors
            raise
        except Exception as e:
            # Catch any other exceptions that might indicate data too large
            error_str = str(e).lower()
            error_type = type(e).__name__
            
            # Check for version-related errors
            if "version" in error_str and ("41" in error_str or "40" in error_str or "invalid" in error_str):
                logger.error(f"QR code data too large: {str(e)}")
                raise ValueError(
                    f"QR code data is too large ({content_length} characters). "
                    f"QR code version exceeds maximum (40). Please use URL-based approach for large data."
                ) from e
            # Check for data overflow
            if "overflow" in error_str or "too large" in error_str or "DataOverflowError" in error_type:
                logger.error(f"QR code data too large ({content_length} chars). Maximum is ~2953 chars.")
                raise ValueError(
                    f"QR code data is too large ({content_length} characters). "
                    f"Maximum recommended size is 2953 characters. Please use URL-based approach."
                ) from e
            # Re-raise unknown exceptions
            raise
        
        # Create image with high quality and proper DPI
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Calculate actual QR code dimensions
        actual_size = img.size[0]
        logger.debug(f"QR code actual size before resize: {actual_size}x{actual_size}")
        
        # Resize if needed (use high-quality resampling)
        # Ensure minimum size for scannability
        min_size = 300
        target_size = max(self.size, min_size)
        
        if img.size[0] != target_size:
            img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
            logger.debug(f"QR code resized to: {target_size}x{target_size}")
        
        # Convert to bytes with high quality
        buffer = io.BytesIO()
        img.save(buffer, format=format, optimize=False)
        buffer.seek(0)
        
        qr_bytes = buffer.getvalue()
        qr_size_bytes = len(qr_bytes)
        logger.info(f"QR code image generated: {qr_size_bytes} bytes, dimensions: {img.size[0]}x{img.size[1]}")
        
        # Verify the data can be read back (for debugging)
        logger.debug(f"QR code contains data: {content[:100]}..." if len(content) > 100 else f"QR code contains data: {content}")
        
        return qr_bytes
    
    def generate_qr_with_logo(
        self,
        data: dict[str, Any] | str,
        logo_path: str,
        logo_size_ratio: float = 0.2,
    ) -> bytes:
        """
        Generate QR code with centered logo.
        
        Args:
            data: Data to encode
            logo_path: Path to logo image
            logo_size_ratio: Logo size relative to QR code
            
        Returns:
            Image bytes with embedded logo
        """
        # Generate base QR
        qr_bytes = self.generate_qr_bytes(data=data)
        qr_image = Image.open(io.BytesIO(qr_bytes))
        
        # Load and resize logo
        logo = Image.open(logo_path)
        logo_size = int(self.size * logo_size_ratio)
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        
        # Calculate position (center)
        pos = ((qr_image.size[0] - logo_size) // 2, (qr_image.size[1] - logo_size) // 2)
        
        # Paste logo
        qr_image.paste(logo, pos)
        
        # Convert back to bytes
        buffer = io.BytesIO()
        qr_image.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer.getvalue()


def get_qr_service() -> QRCodeService:
    """Dependency for QR service."""
    return QRCodeService()
