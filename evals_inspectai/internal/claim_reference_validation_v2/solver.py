"""Inspect AI solver that runs the CitationValidatorAgent against a single section.

The solver builds a `MockFileArtifactsService` populated with the sample's main
document, supporting files, and bibliography items, then invokes the agent with
the same `prompt_kwargs` shape that `validate_section` uses in production.
"""

from typing import Any

from inspect_ai.model import ModelOutput
from inspect_ai.solver import Generate, Solver, TaskState, solver

from evals_inspectai.common.converters import messages_from_langchain
from evals_inspectai.internal.common.config import (
    apply_inspectai_config_to_agent,
    get_runnable_config,
)
from lib.agents.citation_validator import CitationValidatorAgent
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.models.bibliography_item import BibliographyItem
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.workflows.claim_reference_validation_v2.citation_mapping import (
    build_reference_file_map,
)
from tests.conftest import create_test_context

MAIN_FILE_ID = "eval-main"


@solver
def citation_validator_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        meta: dict[str, Any] = state.metadata or {}

        main_file = _build_main_file(meta["main_doc"])
        supporting_files = [
            _build_supporting_file(sf) for sf in meta.get("supporting_files", [])
        ]
        references = [_build_reference(ref) for ref in meta.get("references", [])]

        file_artifacts_service = MockFileArtifactsService(
            main_file=main_file,
            supporting_files=supporting_files,
            references=references,
        )
        context = create_test_context(file_artifacts_service=file_artifacts_service)

        lc_agent = CitationValidatorAgent(context)
        apply_inspectai_config_to_agent(lc_agent)

        section = meta["section"]
        headings = section.get("headings", [])
        prompt_kwargs = {
            "main_file_id": main_file.file_id,
            "start_line": section["start_line"],
            "end_line": section["end_line"],
            "section_headings": " > ".join(headings) if headings else "Document root",
            "reference_file_map": build_reference_file_map(references, supporting_files),
            "domain_context": format_domain_context(meta.get("domain")),
            "audience_context": format_audience_context(meta.get("target_audience")),
            "headings": headings,
        }

        result, lc_messages = await lc_agent.ainvoke(
            prompt_kwargs, config=get_runnable_config()
        )

        state.output = ModelOutput(
            completion=result.model_dump_json(),
            model=lc_agent.model.get_model_name_for_inspectai(),
        )
        state.messages = messages_from_langchain(lc_messages)
        return state

    return solve


def _build_main_file(markdown: str) -> FileDocument:
    return FileDocument(
        file_id=MAIN_FILE_ID,
        file_name="main.md",
        file_path="main.md",
        file_type="text/markdown",
        markdown=markdown,
        markdown_token_count=len(markdown.split()),
    )


def _build_supporting_file(spec: dict[str, Any]) -> FileDocument:
    markdown = spec["markdown"]
    return FileDocument(
        file_id=spec["file_id"],
        file_name=spec.get("file_name", f"{spec['file_id']}.md"),
        file_path=spec.get("file_name", f"{spec['file_id']}.md"),
        file_type="text/markdown",
        markdown=markdown,
        markdown_token_count=len(markdown.split()),
    )


def _build_reference(spec: dict[str, Any]) -> BibliographyItem:
    file_id = spec.get("supporting_file_id")
    return BibliographyItem(
        text=spec["text"],
        has_associated_supporting_document=file_id is not None,
        index_of_associated_supporting_document=spec.get("supporting_index", -1),
        name_of_associated_supporting_document=spec.get(
            "supporting_file_name", ""
        ),
        file_id=file_id,
    )
