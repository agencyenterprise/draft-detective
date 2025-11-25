import asyncio
from pathlib import Path

import pytest

from lib.models.agent_test_case import AgentTestCase
from lib.agents.claim_extractor import (
    ClaimResponse,
    ClaimExtractorAgent,
)
from lib.agents.formatting_utils import format_domain_context, format_audience_context
from tests.conftest import (
    create_test_file_document_from_path,
    data_path,
    extract_paragraph_from_chunk,
    create_test_context,
)
from tests.datasets.loader import load_dataset
from lib.agents.document_summarizer import DocumentSummarizerAgent


TESTS_DIR = Path(__file__).parent.parent

# caching summarized argument
SUMMARIZED_ARGUMENT_CACHE = {}


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(TESTS_DIR / "datasets" / "claim_extractor.yaml")
    dataset = load_dataset(dataset_path)

    test_config = dataset.test_config
    if test_config:
        strict_fields = test_config.strict_fields or set()
        llm_fields = test_config.llm_fields or set()

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        # Load main document from input
        main_path = data_path(test_case.input["main_document"])
        main_doc = asyncio.run(create_test_file_document_from_path(main_path))

        domain = test_case.input.get("domain")
        target_audience = test_case.input.get("target_audience")
        chunk = test_case.input["chunk"]
        paragraph = extract_paragraph_from_chunk(main_doc.markdown, chunk)

        # Store the document for lazy summary generation
        summarized_argument = test_case.input.get("summarized_argument")

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=ClaimExtractorAgent(create_test_context()),
                response_model=ClaimResponse,
                prompt_kwargs={
                    "summarized_argument": summarized_argument,
                    "paragraph": paragraph,
                    "chunk": chunk,
                    "domain_context": format_domain_context(domain),
                    "audience_context": format_audience_context(target_audience),
                    # Store document for lazy generation
                    "_main_doc_markdown": (
                        main_doc.markdown if not summarized_argument else None
                    ),
                    "_file_path": main_path,
                },
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
                fuzzy_threshold=0.75,
                good_match_threshold=0.85,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_claim_extractor_agent_cases(case: AgentTestCase):
    # Generate summary lazily if needed
    # count number of characters in the main_doc_markdown
    main_doc_markdown = case.prompt_kwargs.get("_main_doc_markdown")

    # Handle None case
    if main_doc_markdown is None:
        # Already has summarized_argument, proceed with test
        await case.run()
        eval_result = await case.compare_results()
        assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
        return

    # if number of characters is less than 5000, skip summarized argument generation
    if len(main_doc_markdown) < 5000:
        case.prompt_kwargs["summarized_argument"] = main_doc_markdown

    else:
        # if summarized argument is not provided, generate it
        # access summarized argument cache based on file path
        file_path = case.prompt_kwargs.get("_file_path")
        summarized_argument = SUMMARIZED_ARGUMENT_CACHE.get(file_path)
        if summarized_argument:
            case.prompt_kwargs["summarized_argument"] = summarized_argument
        else:
            # generate summarized argument
            document_summarizer_agent = DocumentSummarizerAgent(create_test_context())
            response = await document_summarizer_agent.ainvoke(
                {"document": main_doc_markdown}
            )
            summarized_argument = response.summary.summary
            SUMMARIZED_ARGUMENT_CACHE[file_path] = summarized_argument
            case.prompt_kwargs["summarized_argument"] = summarized_argument

    await case.run()
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
