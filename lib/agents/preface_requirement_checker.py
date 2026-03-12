"""Preface requirement checker agent for validating preface section requirements.

Prompts loaded from workflow_config.yaml.
"""

from enum import StrEnum
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.config.workflow_config import get_workflow_config
from lib.models.agent import LangChainAgent


class PrefaceRequirementType(StrEnum):
    """Types of preface requirements to check."""

    CONTEXT = "context"
    OBJECTIVES = "objectives"
    RELATIONSHIP = "relationship"
    AUDIENCE = "audience"
    SOURCE_BOILERPLATE = "source_boilerplate"
    SOURCE_FUNDING = "source_funding"


class RequirementCheckResponse(BaseModel):
    """Response from LLM for a requirement check."""

    passed: bool = Field(
        description="True if the requirement is satisfied, False otherwise"
    )
    explanation: str = Field(description="Brief explanation for the pass/fail decision")
    matched_index: int = Field(
        default=-1,
        description="1-indexed position of the sentence/paragraph that satisfies the requirement (-1 if none)",
    )


def _build_sentence_config() -> dict:
    """Build sentence requirement config from YAML."""
    requirements = get_workflow_config("about_this", "requirements")
    config = {}
    for key, req in requirements.items():
        if req.get("level") == "sentence" and req.get("prompt"):
            config[key] = (req.get("name", ""), req.get("prompt", ""))
    return config


SENTENCE_REQUIREMENT_CONFIG = _build_sentence_config()

_sentence_check_prompt = ChatPromptTemplate.from_template(
    """You are an impartial text analyzer verifying preface sections against publication requirements.

## Task
Determine if the provided sentences satisfy the requirement for '{requirement_description}'.

## Requirement
{requirement_prompt}

## Sentences
{numbered_items}

## Instructions
1. Analyze each sentence to determine if it satisfies the requirement.
2. If exactly one sentence satisfies the requirement, set passed=true and matched_index to that sentence number.
3. If multiple sentences could satisfy the requirement, pick the strongest/clearest one.
4. If no sentence satisfies the requirement, set passed=false and matched_index=-1.
5. Provide a brief explanation (1-2 sentences) for your decision.
"""
)

_paragraph_boilerplate_check_prompt = ChatPromptTemplate.from_template(
    """You are an impartial text analyzer checking for CAST boilerplate text.

## Task
Determine if one of the paragraphs contains the Center on AI, Security, and Technology (CAST) boilerplate.

## Expected CAST Boilerplate (or very similar text)
{boilerplate}

## Paragraphs
{numbered_items}

## Instructions
1. Check if any paragraph contains text that is substantially similar to the CAST boilerplate.
2. Minor variations in wording are acceptable, but the core content must match.
3. If found, set passed=true and matched_index to the paragraph number.
4. If not found, set passed=false and matched_index=-1.
5. Provide a brief explanation for your decision.
"""
)

_paragraph_funding_check_prompt = ChatPromptTemplate.from_template(
    """You are an impartial text analyzer checking for funding statements.

## Task
Determine if one of the paragraphs contains an approved funding statement.

## Accepted Funding Statement Patterns
The paragraph should contain text similar to one of these patterns (with appropriate substitutions):
{funding_variants}

## Paragraphs
{numbered_items}

## Instructions
1. Check if any paragraph contains a funding statement that matches one of the accepted patterns.
2. The actual organization names, donors, or sponsors may differ from the examples.
3. Look for statements about: independent research funding, external sponsorship, donor support, or RAND supporter funding.
4. If found, set passed=true and matched_index to the paragraph number.
5. If not found, set passed=false and matched_index=-1.
6. Provide a brief explanation for your decision.
"""
)


class PrefaceRequirementCheckerAgent(LangChainAgent):
    """Agent that checks preface section requirements."""

    name = "Preface Requirement Checker"
    description = (
        "Verifies if a preface section satisfies a specific publication requirement."
    )
    model = gpt_5_mini_model
    temperature = 0.1
    output_schema = RequirementCheckResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> RequirementCheckResponse:
        """Invoke the agent to check a specific requirement."""
        text_items: List[str] = prompt_kwargs["text_items"]
        requirement_type = prompt_kwargs["requirement_type"]

        numbered_items = "\n".join(
            f"{i+1}. {item}" for i, item in enumerate(text_items)
        )

        if requirement_type == PrefaceRequirementType.SOURCE_BOILERPLATE:
            boilerplate = get_workflow_config("about_this", "boilerplate", "")
            messages = _paragraph_boilerplate_check_prompt.format_messages(
                boilerplate=boilerplate,
                numbered_items=numbered_items,
            )
        elif requirement_type == PrefaceRequirementType.SOURCE_FUNDING:
            funding_variants_list = get_workflow_config(
                "about_this", "funding_statement_variants", []
            )
            funding_variants = "\n\n".join(
                f"Pattern {i+1}:\n{variant}"
                for i, variant in enumerate(funding_variants_list[:4])
            )
            messages = _paragraph_funding_check_prompt.format_messages(
                funding_variants=funding_variants,
                numbered_items=numbered_items,
            )
        else:
            description, prompt = SENTENCE_REQUIREMENT_CONFIG.get(
                requirement_type,
                (requirement_type.value, "Check if the requirement is satisfied."),
            )
            messages = _sentence_check_prompt.format_messages(
                requirement_description=description,
                requirement_prompt=prompt,
                numbered_items=numbered_items,
            )

        result = await self.llm.ainvoke(messages, config=config)
        return result
