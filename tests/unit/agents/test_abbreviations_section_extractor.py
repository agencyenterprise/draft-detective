"""Tests for the Abbreviations-section agent's request budget."""

from unittest.mock import MagicMock

from lib.agents.abbreviations_section_extractor import (
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    AbbreviationsSectionExtractorAgent,
)
from lib.services.file_artifacts_service.file_artifacts_service_type import FileArtifactsServiceType
from lib.workflows.context import ContextSchema


def test_section_agent_fails_a_runaway_turn_early_and_retries_it_once() -> None:
    context = ContextSchema(
        openai_api_key="sk-test",
        file_artifacts_service=MagicMock(spec=FileArtifactsServiceType),
        project_id="test-project",
    )
    kwargs = AbbreviationsSectionExtractorAgent(context).get_init_chat_model_kwargs()
    assert kwargs["timeout"] == REQUEST_TIMEOUT_SECONDS < 240
    assert kwargs["max_retries"] == MAX_RETRIES == 1
