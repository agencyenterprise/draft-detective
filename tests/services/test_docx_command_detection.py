import pytest
from lib.services.converters.docx_preprocessor import DocxPreprocessor


def test_detect_soffice_command(monkeypatch):
    """Test that soffice is detected on macOS"""
    import shutil

    def mock_which(cmd):
        if cmd == "soffice":
            return "/usr/local/bin/soffice"
        return None

    monkeypatch.setattr(shutil, "which", mock_which)

    preprocessor = DocxPreprocessor()
    cmd = preprocessor._get_libreoffice_command()

    assert cmd == "soffice"


def test_detect_libreoffice_command(monkeypatch):
    """Test that libreoffice is detected on Linux"""
    import shutil

    def mock_which(cmd):
        if cmd == "libreoffice":
            return "/usr/bin/libreoffice"
        return None

    monkeypatch.setattr(shutil, "which", mock_which)

    preprocessor = DocxPreprocessor()
    cmd = preprocessor._get_libreoffice_command()

    assert cmd == "libreoffice"


def test_prefer_soffice_over_libreoffice(monkeypatch):
    """Test that soffice is preferred when both are available"""
    import shutil

    def mock_which(cmd):
        # Both are available
        if cmd == "soffice":
            return "/usr/local/bin/soffice"
        if cmd == "libreoffice":
            return "/usr/bin/libreoffice"
        return None

    monkeypatch.setattr(shutil, "which", mock_which)

    preprocessor = DocxPreprocessor()
    cmd = preprocessor._get_libreoffice_command()

    # soffice should be preferred (macOS)
    assert cmd == "soffice"


def test_command_caching():
    """Test that command detection is cached"""
    preprocessor = DocxPreprocessor()

    # Manually set the command
    preprocessor._libreoffice_cmd = "test_command"

    # Should return cached value without checking
    cmd = preprocessor._get_libreoffice_command()
    assert cmd == "test_command"


def test_no_libreoffice_raises_error(monkeypatch):
    """Test that missing LibreOffice raises helpful error"""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    preprocessor = DocxPreprocessor()

    with pytest.raises(RuntimeError, match="LibreOffice not found"):
        preprocessor._get_libreoffice_command()

