"""Shared test utilities for all agent tests.

This module provides reusable utilities that work across all agent test suites:
- Path resolution
- Document loading
"""

import os
import shutil
from pathlib import Path

from xxhash import xxh128

from lib.config.env import config
from lib.services.files.document import create_file_document_from_path

TESTS_DIR = Path(__file__).parent


def data_path(path: str) -> str:
    """
    Convert relative test data path to absolute path.

    Args:
        path: Relative path from tests/ directory (e.g., "data/common_knowledge/main.md")

    Returns:
        Absolute path to the file
    """
    return str(TESTS_DIR / path)


async def create_test_file_document_from_path(path: str):
    """
    Load a single document from test data.

    Copies the test file to the uploads directory with an xxhash-based filename,
    similar to how uploaded files are handled in production.

    Args:
        path: Relative path from tests/ directory

    Returns:
        FileDocument object with markdown content
    """
    source_path = data_path(path)

    with open(source_path, "rb") as f:
        content = f.read()

    xxhash = xxh128(content).hexdigest()

    filename = os.path.basename(source_path)
    file_extension = os.path.splitext(filename)[1]

    upload_dir = config.FILE_UPLOADS_MOUNT_PATH
    dest_path = os.path.join(upload_dir, xxhash + file_extension)

    # Copy file to uploads directory atomically (safe for parallel test execution)
    # Use a temp file + rename pattern to avoid race conditions
    os.makedirs(upload_dir, exist_ok=True)
    if not os.path.exists(dest_path):
        temp_path = dest_path + f".{os.getpid()}.tmp"
        try:
            shutil.copy2(source_path, temp_path)
            os.rename(temp_path, dest_path)  # Atomic on POSIX
        except FileExistsError:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    original_file_name = filename

    return await create_file_document_from_path(
        dest_path,
        file_id=path,
        original_file_name=original_file_name,
        markdown_convert=True,
    )
