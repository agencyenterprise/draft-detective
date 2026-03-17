from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FILE_PREFIX = "file://"


def resolve_input(raw_input: str) -> str:
    """Resolve a dataset input value, loading file contents if needed.

    If ``raw_input`` starts with ``file://``, the remainder is treated as a
    path relative to the project root and the file contents are returned.
    Otherwise ``raw_input`` is returned as-is.
    """
    if raw_input.startswith(_FILE_PREFIX):
        file_path = _PROJECT_ROOT / raw_input[len(_FILE_PREFIX) :]
        return file_path.read_text()
    return raw_input
