"""What the overview last read from each run's state, kept per run version.

Reading any path from `state_json` makes Postgres decompress the whole value,
several MB for document processing, and the project page polls the overview
every 3 seconds while a run works. A finished run's state never changes, so
re-reading it on every poll is pure waste.

Every write to a run's state or status moves its `last_updated_at` (the
heartbeat deliberately leaves it alone), so `(run id, last_updated_at)`
names one version of what the overview reads. A cached entry is used only
when the row still carries the same version, so nothing served is stale.
"""

import uuid
from collections import OrderedDict
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from lib.workflows.models import WorkflowError

# Project revisions remembered per process. Each holds one entry per run type,
# a few hundred bytes when the run recorded no errors.
_MAX_REVISIONS = 1024


class RunStateFields(BaseModel):
    """The fields the overview reads out of one run's state."""

    model_config = ConfigDict(frozen=True)

    errors: tuple[WorkflowError, ...] = ()
    ref_count: int | None = None
    main_file_path: str | None = None


class CachedRunState(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: datetime
    fields: RunStateFields


RevisionKey = tuple[str, int]


class RunStateCache:
    """Per project revision, the state fields last read for each of its runs."""

    def __init__(self, max_revisions: int = _MAX_REVISIONS) -> None:
        self._max_revisions = max_revisions
        self._revisions: OrderedDict[RevisionKey, dict[uuid.UUID, CachedRunState]]
        self._revisions = OrderedDict()

    def known(self, key: RevisionKey) -> dict[uuid.UUID, CachedRunState]:
        """A copy of the revision's entries, safe to hold across an await."""
        entries = self._revisions.get(key)
        if entries is None:
            return {}
        self._revisions.move_to_end(key)
        return dict(entries)

    def store(self, key: RevisionKey, entries: dict[uuid.UUID, CachedRunState]) -> None:
        """Replace the revision's entries, so runs no longer listed drop out."""
        self._revisions[key] = entries
        self._revisions.move_to_end(key)
        while len(self._revisions) > self._max_revisions:
            self._revisions.popitem(last=False)

    def clear(self) -> None:
        self._revisions.clear()
