"""
DID (Decentralized Identifier) utility functions.
Generates DIDs using the configured method (evrc).
"""

import time
import random
import string
from typing import Optional

from app.config import get_settings

settings = get_settings()


def generate_random_suffix(length: int = 8) -> str:
    """Generate random alphanumeric suffix."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def generate_did(
    subject_name: str,
    method: Optional[str] = None,
) -> str:
    """
    Generate DID for a subject.
    
    Format: did:{method}:{issuer}:{subject_identifier}
    
    Args:
        subject_name: Human-readable subject name
        method: DID method (default from config)
        
    Returns:
        Generated DID string
    """
    method = method or settings.did_method
    issuer = settings.did_issuer_id
    
    # Create subject identifier from name
    subject_id = subject_name.lower().replace(" ", "-").replace("_", "-")
    
    # Add unique suffix
    suffix = generate_random_suffix(length=6)
    
    return f"did:{method}:{issuer}:{subject_id}-{suffix}"


def generate_presentation_id() -> str:
    """
    Generate unique presentation definition ID.
    
    Format: {timestamp}-{random_suffix}
    
    Returns:
        Unique ID string
    """
    timestamp = int(time.time() * 1000)
    suffix = generate_random_suffix(length=8)
    return f"{timestamp}-{suffix}"


def generate_request_id() -> str:
    """
    Generate unique request ID.
    
    Returns:
        Unique request ID string
    """
    return f"req_{generate_random_suffix(length=12)}"
