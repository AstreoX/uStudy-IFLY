"""API Key encryption utilities for MCP services."""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from config import get_settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the app's secret_key."""
    settings = get_settings()
    # Derive a 32-byte key from secret_key using SHA-256, then base64-encode for Fernet
    key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt an API key for database storage."""
    f = _get_fernet()
    return f.encrypt(plain_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str | None:
    """Decrypt an API key from database storage. Returns None on failure."""
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_key.encode()).decode()
    except (InvalidToken, Exception) as e:
        logger.warning(f"Failed to decrypt API key: {e}")
        return None
