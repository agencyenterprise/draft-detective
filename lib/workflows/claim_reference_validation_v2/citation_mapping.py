"""Utility for building a bibliography-to-file mapping string for agent prompts."""

from typing import List

from lib.models.bibliography_item import BibliographyItem, get_associated_supporting_file
from lib.services.file import FileDocument


def build_reference_file_map(
    references: List[BibliographyItem],
    supporting_files: List[FileDocument],
) -> str:
    """Build a bibliography-to-file mapping for the agent prompt.

    Example output:
        - "Smith et al. (2020). Title..." → File: "study.pdf" (file_id: abc-123)
        - "Doe (2019). Another..." → No supporting file available
    """
    if not references:
        return "No bibliography entries available."

    lines = []
    for ref in references:
        file = get_associated_supporting_file(ref, supporting_files)
        if file:
            lines.append(
                f'- "{ref.text}" → File: "{file.file_name}" (file_id: {file.file_id})'
            )
        else:
            lines.append(f'- "{ref.text}" → No supporting file available')

    return "\n".join(lines)
