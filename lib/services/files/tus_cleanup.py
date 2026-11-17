"""Clean up the TUS router's working directory.

tuspyserver keeps three kinds of file there: each upload's data file (named by its
upload id), its ``.info`` metadata, and a lock file under ``.locks/`` while a chunk
is written. A finished upload's data file moves to permanent storage, but the rest
stays behind, and so does everything of an upload that is abandoned or cut short by
a restart. tuspyserver's own ``gc_files`` can't parse the expiry dates it writes, so
the cleanup is ours.
"""

import logging
import os
import time
from datetime import timedelta

logger = logging.getLogger(__name__)

# Well past tuspyserver's own expiry (``days_to_keep=1``): an upload this old is
# refused by the router anyway, so removing its files can't cut one short.
MAX_AGE = timedelta(days=2)


def remove_upload_info(file_path: str) -> None:
    """Remove the ``.info`` metadata of the upload whose data file is ``file_path``."""
    try:
        os.remove(file_path + ".info")
    except FileNotFoundError:
        pass


def sweep_working_dir(working_dir: str, max_age: timedelta = MAX_AGE) -> int:
    """Remove files in ``working_dir`` and its ``.locks/`` older than ``max_age``.

    Only regular files directly in those two directories are touched; the age is the
    last modification time, which every chunk written refreshes. Returns the count
    removed.
    """
    cutoff = time.time() - max_age.total_seconds()
    removed = 0
    for directory in (working_dir, os.path.join(working_dir, ".locks")):
        try:
            entries = list(os.scandir(directory))
        except FileNotFoundError:
            continue
        for entry in entries:
            removed += _remove_if_older(entry, cutoff)
    if removed:
        logger.info("Removed %d stale TUS upload files from %s", removed, working_dir)
    return removed


def _remove_if_older(entry: os.DirEntry[str], cutoff: float) -> int:
    try:
        if not entry.is_file(follow_symlinks=False):
            return 0
        if entry.stat(follow_symlinks=False).st_mtime >= cutoff:
            return 0
        os.remove(entry.path)
    except FileNotFoundError:
        return 0
    except OSError:
        logger.warning("Could not remove stale TUS upload file %s", entry.path)
        return 0
    return 1
