"""
Upload utilities for direct file uploads.

This module provides a thin wrapper around the upload service for handling
direct multipart form uploads. For resumable uploads, use the upload service directly.
"""

import logging
import uuid
from typing import List

from fastapi import UploadFile

from lib.models.file import File, FileRole
from lib.services.upload.service import finalize_uploaded_file

logger = logging.getLogger(__name__)


async def save_uploaded_files_to_db(
    uploaded_files: List[UploadFile],
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    roles: List[FileRole],
) -> List[File]:
    """
    Save uploaded files to disk and create database records.

    Reuses existing file saving logic (xxhash, deduplication, MIME detection)
    and creates File records in the database for each uploaded file.

    Args:
        uploaded_files: List of files from multipart form upload
        project_id: UUID of the project to associate files with
        user_id: UUID of the user uploading the files
        roles: List of FileRole values matching uploaded_files order

    Returns:
        List of File model instances created in database

    Raises:
        ValueError: If filename is missing or roles length doesn't match files
    """
    if len(roles) != len(uploaded_files):
        raise ValueError(
            f"Number of roles ({len(roles)}) must match number of files ({len(uploaded_files)})"
        )

    file_records = []

    for uploaded_file, role in zip(uploaded_files, roles):
        content = await uploaded_file.read()
        filename = uploaded_file.filename

        if not filename:
            raise ValueError("Uploaded file has no filename")

        # Use shared finalization logic
        file_record = await finalize_uploaded_file(
            content=content,
            filename=filename,
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
        file_records.append(file_record)

    return file_records
