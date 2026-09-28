import base64
import re
from pathlib import Path
from typing import Callable

import yaml
from inspect_ai.dataset import MemoryDataset, Sample

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


# A markdown image whose src is a local path: not a URL, not a data URI, not
# an already-extracted reference.
_LOCAL_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]\n]*)\]\((?!https?://|data:|draftdetective://)(?P<path>[^)\s]+)\)"
)

_IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def references_local_images(markdown: str) -> bool:
    """Whether the document embeds figures from files next to the dataset."""
    return _LOCAL_IMAGE_RE.search(markdown) is not None


def inline_local_images(markdown: str) -> str:
    """The markdown with each local image src replaced by a base64 data URI.

    Dataset inputs stay readable: a figure is written as
    ``![](files/figures/canopy.png)``, a path relative to the evals root, and
    the PNG sits in the repo where a diff viewer renders it. Inlining happens
    at upload time, after which the backend extracts the images and rewrites
    the references exactly as it does for a Word document's pictures. The
    rewrite keeps each image on its own line, so line numbers are unchanged.
    """

    def to_data_uri(match: re.Match[str]) -> str:
        return f"![{match.group('alt')}]({_data_uri(match.group('path'))})"

    return _LOCAL_IMAGE_RE.sub(to_data_uri, markdown)


def local_images(markdown: str) -> list[tuple[str, str]]:
    """Each local image the markdown references, once and in order, as
    ``(path as written, base64 data URI)``: for handing the figures themselves to
    a model that would otherwise see only their paths."""
    paths = dict.fromkeys(m.group("path") for m in _LOCAL_IMAGE_RE.finditer(markdown))
    return [(path, _data_uri(path)) for path in paths]


def _data_uri(relative_path: str) -> str:
    path = _PROJECT_ROOT / relative_path
    mime = _IMAGE_MIME_TYPES.get(path.suffix.lower())
    if mime is None:
        raise ValueError(f"unsupported image type in dataset input: {path.name}")
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


def yaml_dataset(
    path: Path, record_to_sample: Callable[[dict], Sample]
) -> MemoryDataset:
    """Load a YAML list of records as an Inspect dataset.

    Inspect ships CSV and JSON loaders but not YAML. YAML earns this glue: the
    documents are block scalars, so a record reads as one unit in a diff, and
    a figure reference (``![](files/figures/x.png)``) or a table stays legible
    where a JSON string of the same length would not.
    """
    records = yaml.safe_load(path.read_text())
    return MemoryDataset(
        samples=[record_to_sample(record) for record in records],
        name=path.parent.name,
        location=str(path),
    )
