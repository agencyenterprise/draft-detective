"""
Author Rule Checker Agent

Checks individual publication rules for author biographies.
Prompts loaded from workflow_config.yaml.
"""

from enum import StrEnum
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.config.workflow_config import get_workflow_config
from lib.models.agent import LangChainAgent


class AuthorRuleType(StrEnum):
    """Types of rule checks for author bios."""

    POSITION_AFFILIATION = "position_affiliation"  # Rule 2
    PROGRAM_FELLOW = "program_fellow"  # Check for Rule 3 applicability
    PROGRAM_STATEMENT = "program_statement"  # Rule 3
    RESEARCH_FOCUS = "research_focus"  # Rule 4
    HIGHEST_DEGREE = "highest_degree"  # Rule 5


class RuleCheckResponse(BaseModel):
    """Response from rule check."""

    passed: bool = Field(description="Whether the rule check passed")
    explanation: str = Field(description="Brief explanation of the result")


def _build_rule_prompts() -> dict:
    """Build rule prompts from YAML config."""
    rules = get_workflow_config("about_authors", "rules")
    prompts = {}

    if "rule_2_position_affiliation" in rules:
        prompt = rules["rule_2_position_affiliation"].get("prompt")
        if prompt:
            prompts["position_affiliation"] = prompt

    if "rule_3_program_statement" in rules:
        rule = rules["rule_3_program_statement"]
        if rule.get("fellow_prompt"):
            prompts["program_fellow"] = rule["fellow_prompt"]
        if rule.get("program_statement_prompt"):
            prompts["program_statement"] = rule["program_statement_prompt"]

    if "rule_4_research_focus" in rules:
        prompt = rules["rule_4_research_focus"].get("prompt")
        if prompt:
            prompts["research_focus"] = prompt

    if "rule_5_highest_degree" in rules:
        prompt = rules["rule_5_highest_degree"].get("prompt")
        if prompt:
            prompts["highest_degree"] = prompt

    return prompts


RULE_PROMPTS = _build_rule_prompts()


class AuthorRuleCheckerAgent(LangChainAgent):
    """Agent that checks individual publication rules for author bios."""

    name = "Author Rule Checker"
    description = "Check publication rules for author biographies"
    model = gpt_5_mini_model
    temperature = 0.2
    output_schema = RuleCheckResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> RuleCheckResponse:
        """Check a specific rule for an author bio."""
        author_text = prompt_kwargs["author_text"]
        rule_type = prompt_kwargs["rule_type"]

        prompt_template = RULE_PROMPTS[rule_type]
        prompt = ChatPromptTemplate.from_template(prompt_template)
        messages = prompt.format_messages(author_text=author_text)

        result = await self.llm.ainvoke(messages, config=config)
        return result
