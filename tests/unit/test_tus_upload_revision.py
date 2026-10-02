"""Unit tests for revision resolution on TUS uploads.

Reviewer memos review a specific draft, so clients may target a revision other
than the current one. These cover the resolution rules in isolation — no DB, no
HTTP.
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
        assert _parse_role({"role": "reviewer_memo"}) == FileRole.REVIEWER_MEMO


class TestReviewerMemoRevision:
    def test_absent_revision_uses_current(self):
        revision = _resolve_file_revision({}, FileRole.REVIEWER_MEMO, _project(3))
        assert revision == 3

    def test_empty_revision_uses_current(self):
        revision = _resolve_file_revision(
            {"revision": ""}, FileRole.REVIEWER_MEMO, _project(3)
        )
        assert revision == 3

    def test_explicit_earlier_revision_is_honoured(self):
        revision = _resolve_file_revision(
            {"revision": "2"}, FileRole.REVIEWER_MEMO, _project(3)
        )
        assert revision == 2

    def test_whitespace_is_tolerated(self):
        revision = _resolve_file_revision(
            {"revision": " 1 "}, FileRole.REVIEWER_MEMO, _project(3)
        )
        assert revision == 1

    @pytest.mark.parametrize("value", ["abc", "1.0", "-"])
    def test_non_integer_is_rejected(self, value: str):
        with pytest.raises(HTTPException) as exc:
            _resolve_file_revision(
                {"revision": value}, FileRole.REVIEWER_MEMO, _project(3)
            )
        assert exc.value.status_code == 400
        assert "integer" in exc.value.detail

    @pytest.mark.parametrize("value", ["0", "-1", "4", "99"])
    def test_out_of_range_is_rejected(self, value: str):
        with pytest.raises(HTTPException) as exc:
            _resolve_file_revision(
                {"revision": value}, FileRole.REVIEWER_MEMO, _project(3)
            )
        assert exc.value.status_code == 400
        assert "between 1 and 3" in exc.value.detail


class TestResponseMemoRevision:
    def test_absent_revision_uses_current(self):
        assert _resolve_file_revision({}, FileRole.RESPONSE_MEMO, _project(3)) == 3

    def test_tolerates_a_revision_matching_the_current_one(self):
        revision = _resolve_file_revision(
            {"revision": "3"}, FileRole.RESPONSE_MEMO, _project(3)
        )
        assert revision == 3

    def test_rejects_a_back_dated_revision(self):
        # A response memo describes the current draft; attaching it to an older
        # one would have the coverage report read it against the wrong draft.
        with pytest.raises(HTTPException) as exc:
            _resolve_file_revision(
                {"revision": "2"}, FileRole.RESPONSE_MEMO, _project(3)
            )
        assert exc.value.status_code == 400
        assert "response memos" in exc.value.detail


class TestOtherRoles:
    def test_supporting_documents_are_shared_across_revisions(self):
        assert (
            _resolve_file_revision({"revision": "2"}, FileRole.SUPPORT, _project(3))
            is None
        )

    def test_supporting_candidates_are_shared_across_revisions(self):
        # The reference downloader's temporary role. Only MAIN and the memo
        # roles are revision-scoped; anything else must stay NULL.
        assert (
            _resolve_file_revision({}, FileRole.SUPPORTING_CANDIDATE, _project(3))
            is None
        )
        assert (
            _resolve_file_revision(
                {"revision": "2"}, FileRole.SUPPORTING_CANDIDATE, _project(3)
            )
            is None
        )

    def test_main_uses_current_revision(self):
        assert _resolve_file_revision({}, FileRole.MAIN, _project(3)) == 3

    def test_main_tolerates_a_revision_matching_the_current_one(self):
        assert (
            _resolve_file_revision({"revision": "3"}, FileRole.MAIN, _project(3)) == 3
        )

    def test_main_rejects_a_back_dated_revision(self):
        with pytest.raises(HTTPException) as exc:
            _resolve_file_revision({"revision": "1"}, FileRole.MAIN, _project(3))
        assert exc.value.status_code == 400
        assert "main documents" in exc.value.detail
