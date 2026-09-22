"""The proposed-edit redline passes, as one import surface.

Splitting the work up -- what an outcome is, where in a paragraph a redline
goes, which edits get one, and writing them -- keeps each piece small enough to
read, but a caller wants the whole thing and does not care where the lines
fall. So the public names live here, and the modules behind them are free to be
reorganised.

- `tracked_changes_models`: the outcome and plan rows, and the docx-editor
  workspace both passes open.
- `tracked_changes_placement`: where one edit's redline goes in its paragraph,
  or why it cannot go anywhere.
- `tracked_changes_planning`: the read-only pre-flight over every edit.
- `tracked_changes_apply`: what docx-editor is asked to write.
"""

from lib.services.docx.tracked_changes_apply import apply_tracked_changes
from lib.services.docx.tracked_changes_models import (
    TRACKED_CHANGE_AUTHOR,
    EditOutcome,
    EditOutcomeStatus,
    PlannedEdit,
    TrackedChangesPlan,
)
from lib.services.docx.tracked_changes_planning import plan_tracked_changes

__all__ = [
    "TRACKED_CHANGE_AUTHOR",
    "EditOutcome",
    "EditOutcomeStatus",
    "PlannedEdit",
    "TrackedChangesPlan",
    "apply_tracked_changes",
    "plan_tracked_changes",
]
