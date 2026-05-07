from __future__ import annotations

from enum import Enum
from typing import List, Optional

from deepagents import create_deep_agent
from langchain.agents.structured_output import AutoStrategy
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_5_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class FieldProblemTypeV2(str, Enum):
    CORRECT = "correct"
    MISSING = "missing"
    INCORRECT = "incorrect"
    OTHER = "other"


class FieldCategoryV2(str, Enum):
    AUTHOR = "author"
    TITLE = "title"
    PUBLISHER = "publisher"
    YEAR = "year"
    IDENTIFIER = "identifier"


class BibliographyFieldValidationV2(BaseModel):
    category: FieldCategoryV2 = Field(
        description=f"Category of the reference. Possible values: {[e.value for e in FieldCategoryV2]}"
    )
    current_value: str = Field(description="Current value of the reference.")
    suggested_value: str = Field(description="Suggested value of the reference.")
    problem_type: FieldProblemTypeV2 = Field(
        description=f"Problem type of the reference. Must be CORRECT if the only differences are capitalization or minor punctuation. Possible values: {[e.value for e in FieldProblemTypeV2]}"
    )


class ReferenceValidationFinalResultV2(str, Enum):
    # Green: every field was verified CORRECT against an authoritative source.
    CORRECT = "correct"
    # Yellow: at least one field is MISSING but no field is INCORRECT.
    MISSING_FIELDS = "missing_fields"
    # Red: at least one field is INCORRECT, OR the reference could not be found online.
    INCORRECT_FIELDS = "incorrect_fields"


class BibliographyItemValidationV2(BaseModel):
    original_reference: str = Field(description="Original bibliographic item text.")
    final_result: ReferenceValidationFinalResultV2 = Field(
        description=f"Overall validation outcome. Possible values: {[e.value for e in ReferenceValidationFinalResultV2]}"
    )
    bibliography_field_validations: List[BibliographyFieldValidationV2] = Field(
        description="List of reference field validations."
    )
    suggested_action: str = Field(
        description="Suggested action to take if the reference is not valid. A summary of the suggested changes to make the reference valid. If the reference is valid, return 'No changes needed'."
    )
    url: str = Field(description="Found URL for the reference.")
    reasoning: str = Field(
        default="",
        description="Step-by-step reasoning describing your approach to validate the reference.",
    )
    updated_reference: Optional[str] = Field(
        default=None,
        description="Updated reference with the suggested changes made to make the reference valid, matching the format of the original reference. If the reference is already valid, return null.",
    )


_SYSTEM_PROMPT = """\
You are a specialist citation validator. Validate a single bibliographic \
reference by finding the cited work online and comparing it to the reference.

Follow the procedure defined in the reference-validation skill at \
`/skills/reference-validation/SKILL.md`. Read that file before validating — \
it is the single source of truth for the six-step procedure, the field-level \
leniency rules (case/punctuation, name forms, year ±1, publisher \
abbreviations, identifier URL forms, etc.), and the mechanical rules for \
deciding `final_result`.

The next user message contains the reference to validate. Use web search to \
locate the cited work; never validate from memory. Return a structured \
`BibliographyItemValidationV2` result with the field-level validations and \
final outcome.\
"""


class ReferenceValidatorV2Agent(LangChainAgent):
    name = "Reference Validator V2"
    description = "Validate a list of references in a document, by searching for their online presence."
    model = gpt_5_5_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[BibliographyItemValidationV2, list[BaseMessage]]:
        deep_agent = create_deep_agent(
            model=self.llm,
            tools=[{"type": "web_search"}],
            context_schema=ContextSchema,
            response_format=AutoStrategy(BibliographyItemValidationV2),
            skills=["/skills/"],
        )

        result = await deep_agent.ainvoke(
            {
                "files": await self.context.file_artifacts_service.get_deepagent_backend_files(
                    include_supporting_files=False,
                    include_skills=True,
                ),
                "messages": [
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HumanMessage(content=prompt_kwargs["reference"]),
                ],
            },
            config=config,
        )

        return result["structured_response"], result["messages"]
