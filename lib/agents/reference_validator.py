# %%
# reference validator agent
"""
Validates the list of references in a document, by searching for their online presence.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_2_model
from lib.models.agent import DirectOpenAIAgent
from lib.services.openai import ensure_structured_output_response


class FieldProblemType(str, Enum):
    CORRECT = "correct"
    MISSING = "missing"
    INCORRECT = "incorrect"
    OTHER = "other"


class FieldCategory(str, Enum):
    AUTHOR = "author"
    TITLE = "title"
    PUBLISHER = "publisher"
    YEAR = "year"


class BibliographyFieldValidation(BaseModel):
    category: FieldCategory = Field(description="Category of the reference.")
    current_value: str = Field(description="Current value of the reference.")
    suggested_value: str = Field(description="Suggested value of the reference.")
    problem_type: FieldProblemType = Field(description="Problem type of the reference.")


class BibliographyItemValidation(BaseModel):
    original_reference: str = Field(description="Original bibliographic item text.")
    valid_reference: bool = Field(
        description="Whether the original reference is valid."
    )
    bibliography_field_validations: List[BibliographyFieldValidation] = Field(
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
    cited_url: Optional[str] = Field(
        default=None,
        description="The original URL cited in the reference text (before redirect resolution).",
    )


_reference_validator_prompt = PromptTemplate.from_template(
    """Validate a single bibliographic reference by searching for it online and checking its accuracy.

You will receive one reference item from a document's bibliography. Use web search to locate the cited work, then verify each field against the authoritative source you find.

# Validation procedure

1. Search for the reference online to find a matching legitimate source.
2. For each field (author, title, publisher, year), compare the reference's value against what you found online.
3. Determine whether the reference is valid overall.

# Field validation rules

- **Author**: Verify all listed authors exist and names are spelled correctly. Both "first last" and "last, F." formats are acceptable. "et al." is valid for truncating author lists.
- **Title**: Verify the title matches the source. Case differences are not errors. For PDF-linked articles, prefer the title inside the PDF over the webpage title.
- **Publisher**: Verify the publisher matches. Abbreviations are equivalent to full names (e.g., "ACM" = "Association for Computing Machinery").
- **Year**: Verify the publication year is correct.

# Formatting policy

Accept any broadly recognizable citation style (APA, Chicago, MLA, IEEE, etc.). Do not flag minor stylistic differences such as punctuation choice, field ordering, or comma vs. period usage. Focus on content accuracy, not style conformance.

# Bare URL references

A reference consisting solely of a URL with no bibliographic metadata is always invalid. Mark all four fields as MISSING and reconstruct the full citation from the URL's content in updated_reference.

# Output logic

- Set problem_type to CORRECT when the field's value matches the authoritative source (suggested_value equals current_value).
- Set problem_type to MISSING when the field is absent from the reference.
- Set problem_type to INCORRECT when the field is present but wrong.
- Set valid_reference to true only if every field is CORRECT.
- When invalid, write a single-sentence suggested_action summarizing what to fix.
- When invalid, provide updated_reference with corrections applied, preserving the original citation format. When valid, set updated_reference to null.

# Response hygiene

Never include internal search tokens (e.g., turn0search0, turn2search3) or raw metadata markers in any output field. All text must be clean and human-readable.

---

The reference to validate will be provided in the next message."""
)


class ReferenceValidatorAgent(DirectOpenAIAgent):
    name = "Reference Validator"
    description = "Validate a list of references in a document, by searching for their online presence."
    model = gpt_5_2_model
    temperature = 0.0
    output_schema = BibliographyItemValidation

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> BibliographyItemValidation:
        prompt = _reference_validator_prompt.invoke(prompt_kwargs)
        input = [
            {"role": "system", "content": prompt.text},
            {"role": "user", "content": prompt_kwargs["reference"]},
        ]

        response = await self.client.responses.parse(
            model=self.model.name,
            tools=[{"type": "web_search"}],
            max_tool_calls=20,
            reasoning={
                "effort": "low",  # "minimal", "low", "medium", "high"
                "summary": "auto",
            },
            text_format=BibliographyItemValidation,
            input=input,
        )

        return ensure_structured_output_response(response, BibliographyItemValidation)
