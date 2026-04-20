import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet

from lib.config.env import config


def _derive_fernet_key() -> bytes:
    """Derive a valid 32-byte Fernet key from AUTH_SECRET."""
    digest = hashlib.sha256(config.AUTH_SECRET.encode()).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string and return a URL-safe base64 ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a URL-safe base64 ciphertext back to plaintext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
