"""Shared test utilities for all agent tests.

This module provides reusable utilities that work across all agent test suites:
- Path resolution
- Document loading
- Supporting documents formatting
"""

import os
import shutil
from pathlib import Path
from typing import Optional

import nltk  # type: ignore[import-untyped]
from xxhash import xxh128

from lib.config.env import config
from lib.services.file import create_file_document_from_path
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.services.file_artifacts_service.file_artifacts_service_type import FileArtifactsServiceType
from lib.services.vector_store import VectorStoreService

TESTS_DIR = Path(__file__).parent


def pytest_configure(config):
    """Pre-download NLTK data before xdist workers spawn.

    Multiple workers downloading punkt_tab simultaneously race and corrupt the
    archive (BadZipFile), causing test collection to fail in some workers.
    """
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab", quiet=True)


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


def extract_paragraph_from_chunk(full_document: str, chunk: str) -> str:
    """
    Extract paragraph context from chunk.

    For test purposes, we detect the paragraph that contains the chunk breaking the full document into paragraphs.

    In production, state.get_paragraph(chunk.paragraph_index) reconstructs
    the full paragraph from all chunks sharing the same paragraph_index.
    """

    paragraphs = full_document.split("\n")
    for paragraph in paragraphs:
        if chunk in paragraph:
            return paragraph

    raise ValueError(f"Chunk not found in full document: {chunk}")


def create_test_context(
    file_artifacts_service: Optional[FileArtifactsServiceType] = None,
    openai_api_key: Optional[str] = None,
    vector_store: Optional[VectorStoreService] = None,
    user_id: Optional[str] = None,
    project_id: str = "test-project",
    workflow_run_id: Optional[str] = None,
):
    """
    Create a ContextSchema instance for testing agents.

    Returns:
        ContextSchema with test configuration (uses config.OPENAI_API_KEY, no vector_store)
    """
    # Imported lazily to avoid circular imports between conftest and lib.workflows.context
    from lib.workflows.context import ContextSchema

    return ContextSchema(
        openai_api_key=openai_api_key or config.OPENAI_API_KEY,
        vector_store=vector_store
        or VectorStoreService(config.OPENAI_API_KEY or "test-key"),
        project_id=project_id,
        file_artifacts_service=file_artifacts_service or MockFileArtifactsService(),
        user_id=user_id,
        workflow_run_id=workflow_run_id,
    )
