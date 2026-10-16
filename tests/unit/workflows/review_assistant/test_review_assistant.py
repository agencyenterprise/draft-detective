"""The Review Assistant workflow: mounting its inputs and collecting its reports."""

from pathlib import Path

import pytest
from deepagents.backends.utils import file_data_to_string
from docx_editor import Document as EditorDocument

from lib.services.files.document import FileDocument
from lib.workflows.review_assistant.inputs import INPUTS_INDEX_PATH, mount_review_inputs
from lib.workflows.review_assistant.manifest import (
    collect_reports,
    precheck,
    read_input_readings,
)
from lib.workflows.review_assistant.prompt import (
    INPUT_READINGS_PATH,
    REPORT_PATHS,
    build_system_prompt,
)
from lib.workflows.review_assistant.state import (
    ReviewAssistantConfig,
    ReviewAssistantOutput,
    ReviewAssistantState,
)
from lib.workflows.simple_deep_agent.agent_types import (
    DeepAgentRun,
    ReportNotWrittenError,
)
from tests.unit.services.lean_docx import new_document

PLAN = ReviewAssistantOutput.REVISION_PLANNING_SUMMARY
COVERAGE = ReviewAssistantOutput.REVIEWER_COVERAGE_REPORT


def _document(
    file_id: str, name: str, path: str = "", markdown: str = "text"
) -> FileDocument:
    return FileDocument(
        file_id=file_id,
        file_name=name,
        file_path=path or f"/nowhere/{name}",
        file_type="",
        markdown=markdown,
        markdown_token_count=1,
    )


@pytest.fixture
def commented_docx(tmp_path: Path) -> Path:
    document = new_document()
    document.add_paragraph("The survey reached 400 households.")
    path = tmp_path / "draft with comments.docx"
    document.save(str(path))
    doc = EditorDocument.open(
        path, author="Reviewer 2", workspace_dir=str(tmp_path / "ws")
    )
    try:
        doc.add_comment("400 households", "How were these sampled?")
        doc.save()
    finally:
        doc.close()
    return path


def _config(*outputs: ReviewAssistantOutput) -> ReviewAssistantConfig:
    return ReviewAssistantConfig(
        project_id="p", outputs=list(outputs), input_file_ids=["a"]
    )


@pytest.mark.asyncio
async def test_each_document_gets_a_numbered_folder_with_its_text(
    commented_docx: Path,
) -> None:
    mounted = await mount_review_inputs(
        [
            _document("memo", "Reviewer memo.pdf", markdown="# Memo"),
            _document(
                "draft",
                commented_docx.name,
                path=str(commented_docx),
                markdown="# Draft",
            ),
        ]
    )

    assert [i.folder for i in mounted.inputs] == [
        "/inputs/01-reviewer-memo",
        "/inputs/02-draft-with-comments",
    ]
    assert (
        file_data_to_string(mounted.files["/inputs/01-reviewer-memo/document.md"])
        == "# Memo"
    )
    assert "/inputs/01-reviewer-memo/comments.md" not in mounted.files


@pytest.mark.asyncio
async def test_a_word_file_brings_its_comments_beside_its_text(
    commented_docx: Path,
) -> None:
    mounted = await mount_review_inputs(
        [_document("draft", commented_docx.name, path=str(commented_docx))]
    )
    folder = mounted.inputs[0].folder

    comments = file_data_to_string(mounted.files[f"{folder}/comments.md"])
    assert 'Attached to: "400 households"' in comments
    assert "Reviewer 2" in comments
    assert mounted.inputs[0].comment_count == 1
    assert f"{folder}/tracked-changes.md" not in mounted.files

    index = file_data_to_string(mounted.files[INPUTS_INDEX_PATH])
    assert f"`{folder}/comments.md`" in index


@pytest.mark.asyncio
async def test_a_word_file_that_will_not_parse_keeps_its_text() -> None:
    mounted = await mount_review_inputs(
        [_document("bad", "broken.docx", markdown="still here")]
    )

    folder = mounted.inputs[0].folder
    assert file_data_to_string(mounted.files[f"{folder}/document.md"]) == "still here"
    assert mounted.inputs[0].comment_count == 0
    # Its feedback may have been only in the markup, so the loss is reported,
    # to the agent and on the run, not taken for a file without comments.
    [warning] = mounted.markup_warnings
    assert "broken.docx" in warning
    index = file_data_to_string(mounted.files[INPUTS_INDEX_PATH])
    assert "Comments and tracked changes: not read" in index


@pytest.mark.asyncio
async def test_a_legacy_word_file_says_its_markup_was_not_read() -> None:
    mounted = await mount_review_inputs(
        [_document("old", "review.doc", markdown="text")]
    )

    [warning] = mounted.markup_warnings
    assert "legacy Word (.doc)" in warning and "Save it as .docx" in warning


@pytest.mark.asyncio
async def test_a_file_with_no_markup_format_raises_no_warning() -> None:
    mounted = await mount_review_inputs([_document("memo", "memo.md", markdown="text")])

    assert mounted.markup_warnings == []


def test_reports_come_back_in_the_order_asked_and_a_missing_one_is_left_out() -> None:
    state = ReviewAssistantState(config=_config(COVERAGE, PLAN))
    run = DeepAgentRun(files={REPORT_PATHS[PLAN]: "<html>plan</html>"})

    reports = collect_reports(run, state)

    assert [r.output for r in reports] == [PLAN]


def test_a_run_that_wrote_no_report_fails() -> None:
    state = ReviewAssistantState(config=_config(PLAN))
    with pytest.raises(ReportNotWrittenError):
        collect_reports(DeepAgentRun(files={REPORT_PATHS[PLAN]: "  "}), state)


def test_the_agents_reading_of_the_inputs_is_kept_when_it_parses() -> None:
    run = DeepAgentRun(
        files={
            INPUT_READINGS_PATH: '[{"folder": "/inputs/01-x", "role": "reviewer memo", '
            '"reviewer": "Reviewer A", "note": "Signed by the reviewer."}]'
        }
    )
    [reading] = read_input_readings(run)
    assert (reading.role, reading.reviewer) == ("reviewer memo", "Reviewer A")


def test_a_folder_given_with_a_trailing_slash_still_matches_its_input() -> None:
    run = DeepAgentRun(
        files={INPUT_READINGS_PATH: '[{"folder": "/inputs/01-x/", "role": "x"}]'}
    )
    assert [r.folder for r in read_input_readings(run)] == ["/inputs/01-x"]


@pytest.mark.parametrize("raw", ["not json", '{"folder": 1}', '[{"role": "x"}]'])
def test_an_unreadable_reading_costs_only_the_reading(raw: str) -> None:
    assert read_input_readings(DeepAgentRun(files={INPUT_READINGS_PATH: raw})) == []


def test_a_request_needs_an_output_and_a_document() -> None:
    assert (
        precheck(ReviewAssistantConfig(project_id="p", input_file_ids=["a"]))
        is not None
    )
    assert precheck(ReviewAssistantConfig(project_id="p", outputs=[PLAN])) is not None
    assert precheck(_config(PLAN)) is None


def test_the_prompt_asks_for_only_the_outputs_requested() -> None:
    prompt = build_system_prompt([COVERAGE])

    assert REPORT_PATHS[COVERAGE] in prompt
    assert REPORT_PATHS[PLAN] not in prompt
