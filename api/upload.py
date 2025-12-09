import logging
import mimetypes
import os
import uuid
from typing import List

from fastapi import UploadFile
from xxhash import xxh128

from lib.config.env import config
from lib.models.file import File, FileRole
from lib.services.converters.docx_preprocessor import docx_preprocessor
from lib.services.files import create_file_record

logger = logging.getLogger(__name__)


async def save_uploaded_files_to_db(
    uploaded_files: List[UploadFile],
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    roles: List[FileRole],
) -> List[File]:
    """
    Save uploaded files to disk and create database records.

    Reuses existing file saving logic (xxhash, deduplication, docx preprocessing)
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

    upload_dir = config.FILE_UPLOADS_MOUNT_PATH
    file_records = []

    for uploaded_file, role in zip(uploaded_files, roles):
        content = await uploaded_file.read()
        xxhash = xxh128(content).hexdigest()

        filename = uploaded_file.filename
        if not filename or not filename.strip():
            raise ValueError("Uploaded file has no filename")

        # validate filename doesn't contain path separators
        if os.sep in filename or os.altsep and os.altsep in filename:
            raise ValueError("Filename cannot contain path separators")

        file_extension = os.path.splitext(filename)[1]
        file_path = os.path.join(upload_dir, xxhash + file_extension)
        file_size = len(content)

        # Save file if it doesn't already exist
        if os.path.exists(file_path):
            logger.info(
                f"File {filename} with hash {xxhash} already exists in {file_path}, skipping upload"
            )
        else:
            logger.info(f"Saving file {filename} with hash {xxhash} to {file_path}")
            try:
                with open(file_path, "wb") as buffer:
                    if len(content) == 0:
                        logger.warning(f"Uploaded file {filename} is empty!")

                    buffer.write(content)

                if not os.path.exists(file_path):
                    raise Exception(f"File was not created at {file_path}")

            except Exception as e:
                logger.error(f"Error processing uploaded file {filename}: {str(e)}")
                raise

        # Track original file path for .docx files before conversion
        original_file_path = (
            file_path if file_extension.lower() in [".docx", ".doc"] else None
        )

        # Convert .docx to PDF if needed
        try:
            file_path = await docx_preprocessor.convert_to_pdf(file_path)
        except Exception as e:
            logger.error(
                f"Failed to convert {filename} to PDF: {str(e)}. Processing will fail."
            )
            raise

        # Determine MIME type for final file (after conversion)
        file_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        # Create database record
        file_record = await create_file_record(
            project_id=project_id,
            file_name=filename,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            content_hash=xxhash,
            role=role,
            uploaded_by=user_id,
            original_file_path=original_file_path,
        )
        file_records.append(file_record)

    return file_records
