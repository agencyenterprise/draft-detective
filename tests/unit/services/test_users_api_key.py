"""Unit tests for user API key helper functions."""

from unittest.mock import MagicMock, patch

from lib.services.users import get_user_decrypted_api_key


def _make_user(encrypted_key: str | None = None) -> MagicMock:
    user = MagicMock()
    user.encrypted_openai_api_key = encrypted_key
    return user


def test_returns_none_when_no_key_stored():
    user = _make_user(encrypted_key=None)
    assert get_user_decrypted_api_key(user) is None


def test_returns_decrypted_key_when_stored():
    user = _make_user(encrypted_key="encrypted-blob")
    with patch("lib.services.users.decrypt_value", return_value="sk-plaintext") as mock_decrypt:
        result = get_user_decrypted_api_key(user)

    mock_decrypt.assert_called_once_with("encrypted-blob")
    assert result == "sk-plaintext"
