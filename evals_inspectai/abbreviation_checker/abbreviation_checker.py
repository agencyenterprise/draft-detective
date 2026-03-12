from typing import Any

from inspect_ai import Task, task
from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.dataset import FieldSpec, json_dataset
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState

from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.config import (
    apply_inspectai_config_to_agent,
    get_model_or_agent_default,
    get_runnable_config,
)
from evals_inspectai.common.converters import messages_from_langchain
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from lib.agents.abbreviation_checker import AbbreviationCheckerAgent
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.workflows.abbreviation_scan_v2.state import AbbreviationCheckOutput
from tests.conftest import create_test_context


@agent
def abbreviation_checker_agent() -> Agent:
    async def execute(state: AgentState) -> AgentState:
        document_content = state.messages[0].text if state.messages else ""

        main_file = FileDocument(
            file_name="document.md",
            file_path="document.md",
            file_type="text/markdown",
            markdown=document_content,
            markdown_token_count=len(document_content.split()),
            file_id="eval-document",
        )
        file_artifacts_service = MockFileArtifactsService(main_file=main_file)
        context = create_test_context(file_artifacts_service=file_artifacts_service)

        abbr_agent = AbbreviationCheckerAgent(context)
        apply_inspectai_config_to_agent(abbr_agent)

        response, lc_messages = await abbr_agent.ainvoke(
            {}, config=get_runnable_config()
        )

        state.output = ModelOutput(
            completion=response.model_dump_json(),
            model=abbr_agent.model.get_model_name_for_inspectai(),
        )
        state.messages = messages_from_langchain(lc_messages)

        return state

    return execute


@task
def abbreviation_checker():
    dataset = json_dataset(
        "dataset.json",
        FieldSpec(
            target="target_answer",
            metadata=["target_abbreviations_section_found", "target_abbreviations"],
        ),
    )

    return Task(
        dataset=dataset,
        model=get_model_or_agent_default(AbbreviationCheckerAgent),
        solver=abbreviation_checker_agent(),
        scorer=[
            structured_output_scorer(
                AbbreviationCheckOutput, _compare_abbreviation_list
            ),
            structured_output_scorer(
                AbbreviationCheckOutput, _compare_abbreviations_section_found
            ),
            model_graded_check(partial_credit=True),
        ],
    )


def _compare_abbreviations_section_found(
    output: AbbreviationCheckOutput, state: TaskState
) -> bool:
    return (
        str(output.abbreviations_section_found).lower()
        == state.metadata.get("target_abbreviations_section_found", "").lower()
    )


_COMPARE_FIELDS = [
    "inline_definition",
    "line_start",
    "line_end",
    "abbreviations_section_definition",
    "ignored",
]


def _compare_abbreviation_list(
    output: AbbreviationCheckOutput, state: TaskState
) -> Score:
    expected_items: list[dict[str, Any]] = state.metadata.get(
        "target_abbreviations", []
    )
    if not expected_items:
        return Score(value=1.0, explanation="No target abbreviations defined")

    actual_items = [
        item.model_dump(include={"abbr", "occurrence_number", *_COMPARE_FIELDS})
        for item in output.abbreviations
    ]

    return deep_diff_score(expected_items, actual_items)
