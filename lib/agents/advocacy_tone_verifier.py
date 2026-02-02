"""
Advocacy and Tone Verifier Agent

Verifies procedurally-flagged sentences using LLM to confirm and explain
trigger words, advocacy language, or subjective tone issues.

Check type configurations loaded from workflow_config.yaml.
"""

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.config.workflow_config import get_workflow_config
from lib.models.agent import LangChainAgent
from lib.workflows.advocacy_tone.state import AdvocacyToneCheckType


class AdvocacyToneVerificationResponse(BaseModel):
    """Response from LLM verification."""

    confirmed: bool = Field(description="Whether the issue is confirmed after review")
    explanation: str = Field(
        description="Brief explanation (1-2 sentences) of the finding"
    )
    word_positions: List[int] = Field(
        default_factory=list,
        description="1-indexed positions of problematic words in the sentence",
    )


_verification_prompt = ChatPromptTemplate.from_template(
    """You are an impartial text analyzer checking research reports for language issues.

## Task
Analyze the target sentence and determine if it contains {check_type_description}.

## Definitions
{definitions}

## Context (surrounding sentences)
{context}

## Target Sentence to Analyze
{target_sentence}

## Target Sentence Tokenized (positions start at 1)
{tokenized_sentence}

## Instructions
1. Only analyze the TARGET sentence (use context for understanding only)
2. If the issue is confirmed (confirmed = true):
   - Return the 1-indexed word positions causing the issue
   - Provide a clear 1-2 sentence explanation
3. If the issue is NOT confirmed (confirmed = false):
   - Return empty positions list
   - Briefly explain why this is acceptable

Important: Simple, factual mentions of legal terms or policies in an objective context should NOT be flagged.
"""
)


def _build_check_type_configs() -> dict:
    """Build check type configs from YAML."""
    check_types = get_workflow_config("advocacy_tone", "check_types", {})
    configs = {}

    for check_type in AdvocacyToneCheckType:
        yaml_config = check_types.get(check_type.value, {})
        configs[check_type] = {
            "description": yaml_config.get("description", ""),
            "definitions": yaml_config.get("definitions", ""),
        }

    return configs


CHECK_TYPE_CONFIGS = _build_check_type_configs()


class AdvocacyToneVerifierAgent(LangChainAgent):
    """Agent that verifies procedurally-flagged advocacy/tone issues."""

    name = "Advocacy Tone Verifier"
    description = "Verify and explain advocacy/tone issues in text"
    model = gpt_5_mini_model
    temperature = 0.2
    output_schema = AdvocacyToneVerificationResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> AdvocacyToneVerificationResponse:
        """Invoke the agent to verify a flagged sentence.

        Expected prompt_kwargs:
            - check_type: AdvocacyToneCheckType
            - target_sentence: str
            - context: str (surrounding sentences)
        """
        check_type = prompt_kwargs["check_type"]
        check_config = CHECK_TYPE_CONFIGS[check_type]

        # Tokenize the target sentence for position reference
        words = prompt_kwargs["target_sentence"].split()
        tokenized = [{"position": i + 1, "word": w} for i, w in enumerate(words)]

        formatted_kwargs = {
            "check_type_description": check_config["description"],
            "definitions": check_config["definitions"],
            "context": prompt_kwargs["context"],
            "target_sentence": prompt_kwargs["target_sentence"],
            "tokenized_sentence": str(tokenized),
        }

        messages = _verification_prompt.format_messages(**formatted_kwargs)
        result = await self.llm.ainvoke(messages, config=config)

        # Convert 1-indexed positions to 0-indexed for storage
        if result.word_positions:
            result.word_positions = [p - 1 for p in result.word_positions if p > 0]

        return result
