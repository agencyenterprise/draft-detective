"""Unit tests for role and revision resolution on TUS uploads.

Only a main document belongs to a revision, and always to the current one.
These cover the rules in isolation: no DB, no HTTP.
"""

import uuid

import pytest
from fastapi import HTTPException

from lib.api.routers.tus_upload import _parse_role, _resolve_file_revision
from lib.models.file import FileRole
from lib.models.project import Project


def _project(current_revision: int = 3) -> Project:
    return Project(
        id=uuid.uuid4(),
        title="Test Project",
        user_id=uuid.uuid4(),
        current_revision=current_revision,
    )


class TestParseRole:
    def test_defaults_to_support_when_absent(self):
        assert _parse_role({}) == FileRole.SUPPORT

    def test_defaults_to_support_when_invalid(self):
        assert _parse_role({"role": "nonsense"}) == FileRole.SUPPORT

    def test_reads_a_valid_role(self):
        assert _parse_role({"role": "review_input"}) == FileRole.REVIEW_INPUT

    @pytest.mark.parametrize("role", ["reviewer_memo", "response_memo"])
    def test_rejects_the_retired_memo_roles(self, role: str):
        with pytest.raises(HTTPException) as exc:
            _parse_role({"role": role})
        assert exc.value.status_code == 400
        assert "review_input" in exc.value.detail


class TestResolveRevision:
    @pytest.mark.parametrize(
        "role", [FileRole.SUPPORT, FileRole.SUPPORTING_CANDIDATE, FileRole.REVIEW_INPUT]
    )
    def test_other_roles_are_shared_across_revisions(self, role: FileRole):
        assert _resolve_file_revision({}, role, _project(3)) is None
        assert _resolve_file_revision({"revision": "2"}, role, _project(3)) is None

    def test_main_uses_current_revision(self):
        assert _resolve_file_revision({}, FileRole.MAIN, _project(3)) == 3

    @pytest.mark.parametrize("value", ["3", " 3 ", ""])
    def test_main_tolerates_the_current_revision_or_none(self, value: str):
        assert (
            _resolve_file_revision({"revision": value}, FileRole.MAIN, _project(3)) == 3
        )

    def test_main_rejects_a_back_dated_revision(self):
        with pytest.raises(HTTPException) as exc:
            _resolve_file_revision({"revision": "1"}, FileRole.MAIN, _project(3))
        assert exc.value.status_code == 400
        assert "main documents" in exc.value.detail
