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

    needs_substantiation: bool = Field(
        description=(
            "Whether the claim needs to be substantiated "
            "by references and/or evidence"
        )
    )

    rationale: str = Field(
        description=(
            "The rationale for why the claim needs to be substantiated "
            "by references and/or evidence"
        )
    )

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
You are an expert at identifying factual claims that require external verification. \
Your task is to analyze the provided text and identify claims that need to be \
substantiated by sources, references, or evidence.

Focus on claims that:
- Assert facts, statistics, or empirical statements that readers would need to verify
- Make claims about causality, correlations, or relationships that require scholarly support
- State opinions presented as facts that would benefit from authoritative backing
- Contains citations to external sources that need to be verified
- Include historical, scientific, or technical assertions that depend on external sources

For each claim you identify, provide:
1. **key_sentence**: The exact sentence(s) containing the claim
2. **claim**: A clear paraphrase of the claim being made
3. **needs_substantiation**: Whether the claim requires external sources/references \
to be credible (True) or is self-evident/common knowledge (False)
4. **rationale**: Why the claim does or does not need external verification
5. **central**: Whether the claim is central to the overall argument of the document
6. **centrality_rationale**: Why the claim is or is not central to the argument

## Instructions
- Scan the text for factual assertions, empirical claims, and statements that imply verification
- Prioritize claims that would be strengthened by citations, studies, or authoritative sources
- Distinguish claims needing substantiation from common knowledge or self-evident statements
- Be precise in extracting the exact claim being made

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

    def create_llm(self):
        return init_chat_model(
            self.model.model_name,
            temperature=self.temperature,
            timeout=self.timeout,
            api_key=self.context.openai_api_key,
        )

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
