"""Unit tests for the encryption service."""

from unittest.mock import patch

import pytest

from lib.services.encryption import decrypt_value, encrypt_value


def test_encrypt_returns_string():
    result = encrypt_value("hello")
    assert isinstance(result, str)


def test_encrypt_differs_from_plaintext():
    plaintext = "sk-secret-api-key"
    assert encrypt_value(plaintext) != plaintext


def test_round_trip():
    plaintext = "sk-openai-test-key-12345"
    assert decrypt_value(encrypt_value(plaintext)) == plaintext


def test_round_trip_empty_string():
    assert decrypt_value(encrypt_value("")) == ""


def test_each_encryption_produces_different_ciphertext():
    """Fernet uses random IVs, so two encryptions of the same value differ."""
    plaintext = "same-key"
    assert encrypt_value(plaintext) != encrypt_value(plaintext)


def test_decrypt_with_wrong_key_raises():
    ciphertext = encrypt_value("original")
    with patch("lib.services.encryption.config") as mock_cfg:
        mock_cfg.AUTH_SECRET = "completely-different-secret-for-testing"
        # Clear the lru_cache so the patched config is used
        from lib.services.encryption import _get_fernet
        _get_fernet.cache_clear()
        with pytest.raises(Exception):
            decrypt_value(ciphertext)
    # Restore cache state for subsequent tests
    from lib.services.encryption import _get_fernet
    _get_fernet.cache_clear()
