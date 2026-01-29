"""
Author Final Judge Agent

Summarizes failed rules and provides guidance for improving author bios.
"""

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class FinalJudgeResponse(BaseModel):
    """Response from final judge."""

    comment: str = Field(description="Brief summary of why the bio failed")
    guidance: str = Field(description="Actionable guidance on how to fix it")


_judge_prompt = ChatPromptTemplate.from_template(
    """The following author bio failed some quality checks:

## Failed Rules
{failed_rules}

## Author Bio
{author_text}

## Instructions
Provide:
1. A brief one-sentence explanation summarizing why the bio did not pass
2. Concise, actionable guidance on how to improve it
"""
)


class AuthorFinalJudgeAgent(LangChainAgent):
    """Agent that summarizes failures and provides improvement guidance."""

    name = "Author Final Judge"
    description = "Summarize failed rules and provide improvement guidance"
    model = gpt_5_mini_model
    temperature = 0.3
    output_schema = FinalJudgeResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> FinalJudgeResponse:
        """Generate summary and guidance for a failed author bio.

        Expected prompt_kwargs:
            - author_text: str (the full author bio text)
            - failed_rules: List[str] (list of failed rule explanations)
        """
        author_text = prompt_kwargs["author_text"]
        failed_rules = prompt_kwargs["failed_rules"]

        failed_rules_str = "\n".join(f"- {rule}" for rule in failed_rules)

        messages = _judge_prompt.format_messages(
            author_text=author_text,
            failed_rules=failed_rules_str,
        )
        result = await self.llm.ainvoke(messages, config=config)

        return result
