"""Tests for anchoring an issue's Word comment on its passage instead of its paragraph."""

import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from docx import Document
from docx.oxml.ns import qn
from docx.oxml.parser import OxmlElement
from docx_editor import Document as EditorDocument
from docx_editor import EditOperation
from lxml import etree

from lib.models.issue import Issue
from lib.services.docx.comment_anchors import CommentAnchor, plan_comment_anchors
from lib.services.docx.comment_runs import anchored_runs
from lib.services.docx.manipulator import DocxComment, DocxManipulatorService
from lib.workflows.models import SeverityEnum, WorkflowRunType
from tests.unit.services.docx.lean_docx import new_document

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _commented_text(path: Path) -> dict[str, str]:
    """``{comment id: the visible text inside its range}`` for a saved file.

    Deleted text is left out and inserted text kept, as Word shows the range
    with its tracked changes.
    """
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    open_ranges: set[str] = set()
    covered: dict[str, str] = {}
    for element in root.iter():
        comment_id = element.get(f"{_W}id", "")
        if element.tag == f"{_W}commentRangeStart":
            open_ranges.add(comment_id)
            covered.setdefault(comment_id, "")
        elif element.tag == f"{_W}commentRangeEnd":
            open_ranges.discard(comment_id)
        elif element.tag == f"{_W}t" and element.text:
            for open_id in open_ranges:
                covered[open_id] += element.text
    return covered


def _three_run_paragraph(document):
    paragraph = document.add_paragraph()
    paragraph.add_run("The quick brown ")
    paragraph.add_run("fox jumps").bold = True
    paragraph.add_run(" over the lazy dog.")
    return paragraph


class TestAnchoredRuns:
    def test_the_edge_runs_are_split_so_the_comment_covers_the_passage_alone(
        self, tmp_path: Path
    ):
        document = new_document()
        paragraph = _three_run_paragraph(document)

        runs = anchored_runs(paragraph, "brown fox", occurrence=0, total=1)
        assert runs is not None
        document.add_comment(runs=runs, text="note", author="DD", initials="DD")
        path = tmp_path / "out.docx"
        document.save(str(path))

        assert list(_commented_text(path).values()) == ["brown fox"]
        reopened = Document(str(path)).paragraphs[0]
        assert reopened.text == "The quick brown fox jumps over the lazy dog."
        # The split halves keep their formatting. (The empty run is the
        # comment's reference mark.)
        assert [(r.text, bool(r.bold)) for r in reopened.runs if r.text] == [
            ("The quick ", False),
            ("brown ", False),
            ("fox", True),
            (" jumps", True),
            (" over the lazy dog.", False),
        ]

    def test_the_occurrence_picks_which_repeat_is_covered(self, tmp_path: Path):
        document = new_document()
        paragraph = document.add_paragraph("one cat, two cat, three cat")

        runs = anchored_runs(paragraph, "cat", occurrence=1, total=3)
        assert runs is not None
        document.add_comment(runs=runs, text="note", author="DD", initials="DD")
        path = tmp_path / "out.docx"
        document.save(str(path))

        assert list(_commented_text(path).values()) == ["cat"]
        assert Document(str(path)).paragraphs[0].runs[0].text == "one cat, two "

    def test_a_run_holding_more_than_text_is_covered_whole_rather_than_split(self):
        document = new_document()
        paragraph = document.add_paragraph()
        run = paragraph.add_run("before")
        run._r.append(OxmlElement("w:tab"))
        tail = OxmlElement("w:t")
        tail.text = "after"
        run._r.append(tail)

        runs = anchored_runs(paragraph, "fore", occurrence=0, total=1)

        assert runs is not None
        assert runs[0] is not None and runs[0]._r is run._r
        assert paragraph.runs[0]._r.find(qn("w:tab")) is not None

    def test_a_count_python_docx_does_not_see_gives_up(self):
        document = new_document()
        paragraph = document.add_paragraph("one cat only")

        # docx-editor saw two, so its occurrence does not index this text.
        assert anchored_runs(paragraph, "cat", occurrence=1, total=2) is None
        assert anchored_runs(paragraph, "dog", occurrence=0, total=1) is None


def _issue(passage_text: str | None, *, line: int = 1, display: str | None = None):
    now = datetime.now(UTC)
    return Issue(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        workflow_run_id=uuid.uuid4(),
        issue_hash=uuid.uuid4().hex,
        title="Trigger word",
        description="Certainty language.",
        severity=SeverityEnum.MEDIUM,
        workflow_type=WorkflowRunType.ADVOCACY_TONE_V2,
        start_line=line,
        end_line=line,
        passage_text=passage_text,
        passage_display_text=display or passage_text,
        passage_display_occurrence=0 if passage_text else None,
        passage_line=line if passage_text else None,
        created_at=now,
        updated_at=now,
    )


class TestPlanCommentAnchors:
    @pytest.fixture
    def docx_path(self, tmp_path: Path) -> Path:
        document = new_document()
        document.add_paragraph("We will certainly succeed.")
        document.add_paragraph("A second paragraph, certainly.")
        path = tmp_path / "main.docx"
        document.save(str(path))
        return path

    _MARKDOWN = "We will certainly succeed.\n\nA second paragraph, certainly."
    _RANGES = {0: (1, 2), 1: (3, 3)}

    @pytest.mark.asyncio
    async def test_a_passage_is_anchored_in_its_own_paragraph(
        self, docx_path: Path, tmp_path: Path
    ):
        first = _issue("certainly succeed", line=1)
        second = _issue("certainly", line=3)
        whole_line = _issue(None)

        anchors = await plan_comment_anchors(
            [first, second, whole_line],
            self._MARKDOWN,
            str(docx_path),
            self._RANGES,
            workspace_root=str(tmp_path),
        )

        assert anchors[first.id] == CommentAnchor(
            paragraph_index=0, find="certainly succeed", occurrence=0, total=1
        )
        assert anchors[second.id].paragraph_index == 1
        assert anchors[second.id].find == "certainly"
        assert whole_line.id not in anchors

    @pytest.mark.asyncio
    async def test_a_passage_the_paragraph_lacks_falls_back(
        self, docx_path: Path, tmp_path: Path
    ):
        gone = _issue("no longer there", line=1)

        anchors = await plan_comment_anchors(
            [gone], self._MARKDOWN, str(docx_path), self._RANGES, str(tmp_path)
        )

        assert anchors == {}

    @pytest.mark.asyncio
    async def test_without_any_passage_the_document_is_never_opened(
        self, tmp_path: Path
    ):
        missing = tmp_path / "does-not-exist.docx"

        anchors = await plan_comment_anchors(
            [_issue(None)], self._MARKDOWN, str(missing), self._RANGES
        )

        assert anchors == {}


class TestAnchoredCommentsWithRedlines:
    def test_the_comment_stays_on_its_words_when_a_redline_crosses_them(
        self, tmp_path: Path
    ):
        source = tmp_path / "main.docx"
        document = new_document()
        _three_run_paragraph(document)
        document.save(str(source))

        service = DocxManipulatorService()
        commented = Path(
            service._add_comments_to_docx_sync(
                str(source),
                [
                    DocxComment(
                        paragraph_index=0,
                        comment_text="Passage comment",
                        anchor=CommentAnchor(
                            paragraph_index=0, find="brown fox", occurrence=0, total=1
                        ),
                    ),
                    DocxComment(paragraph_index=0, comment_text="Whole paragraph"),
                ],
                workflow_run_id=uuid.uuid4().hex,
            )
        )

        assert sorted(_commented_text(commented).values()) == [
            "The quick brown fox jumps over the lazy dog.",
            "brown fox",
        ]

        editor = EditorDocument.open(
            commented,
            author="Draft Detective",
            workspace_dir=str(tmp_path / "ws"),
            force_recreate=True,
        )
        try:
            ref = editor.list_paragraphs_structured(limit=None)[0].ref
            editor.batch_edit(
                [
                    EditOperation.replace(
                        paragraph=ref,
                        find="brown fox jumps",
                        replace_with="red fox leaps",
                    )
                ]
            )
            editor.save()
        finally:
            editor.close()

        # The range markers survive the redline and still sit on the passage:
        # the deleted words are out of view, the inserted ones inside it.
        assert sorted(_commented_text(commented).values()) == [
            "The quick red fox leaps over the lazy dog.",
            "red fox leaps",
        ]


@pytest.fixture(autouse=True)
def _uploads_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the export's output directory at the test's own folder."""
    monkeypatch.setattr(
        "lib.services.docx.manipulator.config.FILE_UPLOADS_MOUNT_PATH", str(tmp_path)
    )
