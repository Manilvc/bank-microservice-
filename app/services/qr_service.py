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
            data: Data to encode (dict will be JSON serialized, str will be used as-is)
            format: Image format (PNG, JPEG)
            
        Returns:
            Image bytes
        """
        # Convert dict to JSON string if needed
        if isinstance(data, dict):
            content = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        else:
            content = str(data)
        
        # Generate QR code with logo and convert into bytes
        qr_code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
        qr_code.add_data(content)
        qr_code.make()
        image = qr_code.make_image().convert('RGBA')
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        imgByteArr = buffered.getvalue()
        
        return imgByteArr
    
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
