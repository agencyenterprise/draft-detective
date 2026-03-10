from inspect_ai import Task, task
from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.dataset import Sample, json_dataset
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
from evals_inspectai.common.loaders import resolve_input
from evals_inspectai.common.scorers import structured_output_scorer
from lib.agents.reference_text_extractor_v2 import (
    ReferenceExtractorV2Agent,
    ReferenceExtractorV2Output,
)
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from tests.conftest import create_test_context


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=resolve_input(record["input"]),
        metadata={"target_references": record.get("target_references", [])},
    )


@agent
def reference_text_extractor_agent() -> Agent:
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

        ref_agent = ReferenceExtractorV2Agent(context)
        apply_inspectai_config_to_agent(ref_agent)

        response, lc_messages = await ref_agent.ainvoke(
            {}, config=get_runnable_config()
        )

        state.output = ModelOutput(
            completion=response.model_dump_json(),
            model=ref_agent.model.get_model_name_for_inspectai(),
        )
        state.messages = messages_from_langchain(lc_messages)

        return state

    return execute


@task
def reference_text_extractor():
    dataset = json_dataset("dataset.json", _record_to_sample)

    return Task(
        dataset=dataset,
        model=get_model_or_agent_default(ReferenceExtractorV2Agent),
        solver=reference_text_extractor_agent(),
        scorer=[
            structured_output_scorer(ReferenceExtractorV2Output, _compare_references),
        ],
    )


def _compare_references(output: ReferenceExtractorV2Output, state: TaskState) -> Score:
    expected_refs: list[str] = state.metadata.get("target_references", [])
    actual_refs = [ref.text for ref in output.references]
    return deep_diff_score(expected_refs, actual_refs)
