"""Persistence for images extracted from uploaded documents.

Extracted images live in the ``files`` table like every other on-disk binary,
under role EXTRACTED_IMAGE with ``parent_file_id`` pointing at the document
they came from. They are served by the regular file-download endpoint and are
deleted with their parent (FK cascade for the rows, ``delete_project_files``
for the disk files).
"""

import os
import uuid

from sqlalchemy import delete, select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.file import File, FileRole
from lib.services.files.service import (
    _delete_file_from_disk,
    _is_path_shared,
    get_file_by_id,
)
from lib.services.image_extraction import ExtractedImage


async def replace_extracted_images(
    parent_file_id: uuid.UUID | str, images: list[ExtractedImage]
) -> None:
    """Replace the extracted-image rows for a file.

    Wholesale replacement keeps reconversion idempotent: the parent's markdown
    references images by the ids generated at extraction time, so rows from a
    previous conversion must never survive alongside new ones. Their disk
    files go too when nothing references them anymore — cleanup discovers
    disk files only through rows, so skipping this would strand them forever
    when a reconversion produces different bytes (e.g. rendering changed).
    """
    parent = await get_file_by_id(parent_file_id)
    incoming_paths = {image.image_path for image in images}

    async with get_async_db_session() as session:
        previous_stmt = select(File).where(col(File.parent_file_id) == parent.id)
        previous = [
            (row.file_path, row.id)
            for row in (await session.execute(previous_stmt)).scalars()
        ]

        await session.execute(delete(File).where(col(File.parent_file_id) == parent.id))

        stale_paths: list[str] = []
        for path, row_id in previous:
            # The new rows are not inserted yet, so paths they will reference
            # must be treated as still in use.
            if path in incoming_paths:
                continue
            if not await _is_path_shared(session, path, row_id):
                stale_paths.append(path)

        for position, image in enumerate(images):
            extension = os.path.splitext(image.image_path)[1]
            session.add(
                File(
                    id=image.id,
                    project_id=parent.project_id,
                    file_name=f"image-{position + 1}{extension}",
                    file_path=image.image_path,
                    file_type=image.mime_type,
                    file_size=image.file_size,
                    content_hash=image.content_hash,
                    role=FileRole.EXTRACTED_IMAGE,
                    uploaded_by=parent.uploaded_by,
                    description=image.alt or None,
                    revision=parent.revision,
                    parent_file_id=parent.id,
                )
            )
        await session.commit()

    # Disk cleanup strictly after the commit: a failed transaction restores
    # the old rows, and restored rows must never point at deleted files.
    for path in stale_paths:
        _delete_file_from_disk(path)
