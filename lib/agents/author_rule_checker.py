"""
Author Rule Checker Agent

Checks individual publication rules for author biographies.
Handles rules 2-5 and TASP fellow detection.
"""

from enum import StrEnum
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class AuthorRuleType(StrEnum):
    """Types of rule checks for author bios."""

    POSITION_AFFILIATION = "position_affiliation"  # Rule 2
    TASP_FELLOW = "tasp_fellow"  # Check for Rule 3 applicability
    TASP_STATEMENT = "tasp_statement"  # Rule 3
    RESEARCH_FOCUS = "research_focus"  # Rule 4
    HIGHEST_DEGREE = "highest_degree"  # Rule 5


class RuleCheckResponse(BaseModel):
    """Response from rule check."""

    passed: bool = Field(description="Whether the rule check passed")
    explanation: str = Field(description="Brief explanation of the result")


# Prompts for each rule type (matching reference implementation)
RULE_PROMPTS = {
    AuthorRuleType.POSITION_AFFILIATION: """Verify whether the following author description contains the author's 
current position and overall affiliation with RAND or another organization.

Valid examples:
- "[Author] is a senior statistician at RAND"
- "[Author] is an associate professor at [University] and an adjunct senior research engineer with RAND"

Respond with passed=true if the position and affiliation are present, passed=false otherwise.
Provide a brief explanation.

Author description:
{author_text}""",
    AuthorRuleType.TASP_FELLOW: """Based on the following author description, is the author identified 
as a Technology and Security Policy (TASP) fellow?

Respond with passed=true if the author IS a TASP fellow, passed=false otherwise.
Provide a brief explanation.

Author description:
{author_text}""",
    AuthorRuleType.TASP_STATEMENT: """Verify whether the author description includes the required TASP statement:
"[Author] is [any non-RAND affiliation or position and] a Technology and Security Policy fellow at RAND; 
for more information on the fellowship program, visit www.rand.org/tasp-fellows"

The key requirements are:
1. Mention of "Technology and Security Policy fellow at RAND"
2. The URL "www.rand.org/tasp-fellows"

Respond with passed=true if the statement is present, passed=false otherwise.
Provide a brief explanation.

Author description:
{author_text}""",
    AuthorRuleType.RESEARCH_FOCUS: """Does the author description contain a research focus?

Valid examples:
- "[Pronoun] conducts technical and policy research on such topics as cybersecurity, privacy..."
- "[Pronoun]'s research interests include..."
- "[Pronoun] focuses on research related to..."

Respond with passed=true if a research focus is present, passed=false otherwise.
Provide a brief explanation.

Author description:
{author_text}""",
    AuthorRuleType.HIGHEST_DEGREE: """Does the following author description contain highest degree attained 
and associated field (e.g., "[Author] holds a Ph.D. in macroeconomics")?

Instructions:
- It is okay if only a single academic degree is mentioned (don't assume a higher degree exists)
- It is okay if the author is a Ph.D. student (no highest degree required)
- Multiple degrees at the same level are acceptable (e.g., "MPhil in Science and M.Sc. in Physics")
- Omit other education details like year or institution

Respond with passed=true if the highest degree is mentioned, passed=false otherwise.
Provide a brief explanation.

Author description:
{author_text}""",
}


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
        """Check a specific rule for an author bio.

        Expected prompt_kwargs:
            - author_text: str (the full author bio text)
            - rule_type: AuthorRuleType (which rule to check)
        """
        author_text = prompt_kwargs["author_text"]
        rule_type = prompt_kwargs["rule_type"]

        prompt_template = RULE_PROMPTS[rule_type]
        prompt = ChatPromptTemplate.from_template(prompt_template)
        messages = prompt.format_messages(author_text=author_text)

        result = await self.llm.ainvoke(messages, config=config)
        return result

