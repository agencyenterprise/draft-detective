"""
Upload utilities for direct multipart form uploads.
For resumable uploads, use the tus_upload router.
"""

import uuid
from typing import List

from fastapi import UploadFile

from lib.models.file import File, FileRole
from lib.services.file_finalization import finalize_file


async def save_uploaded_files_to_db(
    uploaded_files: List[UploadFile],
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    roles: List[FileRole],
) -> List[File]:
    """Save uploaded files to disk and create database records."""
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

        file_record = await finalize_file(
            content=content,
            filename=filename,
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
        file_records.append(file_record)

    return file_records
