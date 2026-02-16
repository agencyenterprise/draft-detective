"""
Claim Extractor V2 Agent

Analyzes text for claims that need to be substantiated by sources,
references, or evidence. Operates on paragraph-level text (not individual
chunks), making it suitable for batched paragraph-group extraction.
"""

from typing import Optional

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


# =========================
#  Pydantic data contracts
# =========================


class ClaimV2(BaseModel):
    """A single factual claim with verification properties."""

    key_sentence: str = Field(
        description="The key sentence that contains the claim that needs to be verified."
    )

    claim: str = Field(description="The claim made in the text")

    needs_external_verification: bool = Field(
        description=(
            "Whether the claim needs external verification "
            "by references and/or evidence"
        )
    )

    rationale: str = Field(description=("For why the key sentence implies the claim"))

    central: bool = Field(
        description="Whether the claim is central to the argument of the document"
    )

    centrality_rationale: Optional[str] = Field(
        default=None,
        description=(
            "The rationale for why you think the claim is central "
            "or is not central to the argument of the document"
        ),
    )


class ClaimResponseV2(BaseModel):
    claims: list[ClaimV2] = Field(
        description="A list of claims made in the chunk of text"
    )
    rationale: str = Field(
        description=(
            "Overall rationale for why you think "
            "the chunk of text implies these claims"
        )
    )


# =========================
#  Prompt Template
# =========================

_claim_extractor_v2_prompt = ChatPromptTemplate.from_template(
    """
## Task
You are an expert at extracting and analyzing factual claims from documents. \
Your task is to identify all substantive factual claims in the provided text \
and then assess whether each claim needs external verification.

## Step 1: Extract All Substantive Claims
Identify every decontextualized factual claim in the text. A claim is a declarative \
assertion or proposition that can be understood and evaluated in isolation. Include claims that:
- Assert facts, statistics, or empirical statements
- Make claims about causality, correlations, or relationships
- State opinions presented as facts
- Reference or cite external sources
- Include historical, scientific, or technical assertions
- Describe established knowledge, definitions, or widely accepted principles

Do NOT extract:
- Titles, headings, or labels that are not declarative statements
- Bibliographic entries or reference list items
- Duplicate claims already captured elsewhere in the output

Each claim must be specific and decontextualized: it should be fully understandable \
in isolation without needing surrounding text for context.

## Step 2: Classify Each Claim
For each extracted claim, determine:
1. **key_sentence**: The exact sentence(s) from the text containing the claim
2. **claim**: A clear, self-contained paraphrase of the claim being made
3. **needs_external_verification**: Whether the claim requires external sources, \
references, or evidence to be credible (True), or is self-evident, common knowledge, \
or logically derived from already-substantiated premises (False)
4. **rationale**: Why the claim does or does not need external verification
5. **central**: Whether the claim is central to the overall argument of the document
6. **centrality_rationale**: Why the claim is or is not central to the argument

## Instructions
- Scan the text for factual assertions, empirical claims, and statements that imply verification
- Prioritize claims that would be strengthened by citations, studies, or authoritative sources
- Distinguish claims needing substantiation from common knowledge or self-evident statements
- Be precise in extracting the exact claim being made

## Additional Guidelines
- The input text may contain multiple paragraphs from different sections of a document.
- Section heading markers like `[Section: ...]` indicate which part of the document the \
following paragraphs belong to. Use these markers to understand the context of the text.
- Do NOT extract claims from non-analytic sections of the document. Specifically, skip \
content that falls under sections such as funding statements, acknowledgments, references, \
bibliography, "About the Authors", or other document metadata sections. If a section heading \
suggests the content is administrative or bibliographic rather than analytical, return no \
claims for that content.
- Only extract claims from the main analytical content of the document (e.g., introduction, \
methods, results, discussion, findings, analysis).

## Text to Analyze
```
{text}
```
"""
)

# =========================
#  Agent Implementation
# =========================


class ClaimExtractorV2Agent(LangChainAgent):
    """Agent that extracts claims from text (paragraph groups)."""

    name = "Claim Extractor v2"
    description = "Extract claims from text"
    model = gpt_5_mini_model
    temperature = 0.2
    output_schema = ClaimResponseV2
    reasoning = {"effort": "low", "summary": "auto"}

    def create_llm(self):
        init_kwargs = self.get_init_chat_model_kwargs()
        return init_chat_model(**init_kwargs)

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> ClaimResponseV2:
        agent = create_agent(
            self.llm,
            tools=[],
            context_schema=ContextSchema,
            system_prompt=None,
            response_format=ClaimResponseV2,
        )

        messages = _claim_extractor_v2_prompt.format_messages(**prompt_kwargs)

        result = await agent.ainvoke(
            {"messages": messages},
            config={"recursion_limit": 50, **(config or {})},
            context=self.context,
        )

        return result["structured_response"]
