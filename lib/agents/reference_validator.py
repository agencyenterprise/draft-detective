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

from lib.config.llm_models import gpt_5_mini_model
from lib.agents.base import DirectOpenAIAgent
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


_reference_validator_prompt = PromptTemplate.from_template(
    """
You are an expert reference validator. Your task is to validate a reference from a document by ensuring there is online presence from a legitimate source.

# Reference Field Categories and what to check
- AUTHOR (The author of the reference): Check if all the authors are present and their names are spelled correctly.
- TITLE (The title of the reference): Check that the title of the reference is correct
- PUBLISHER (The publisher of the reference): Check that the publisher of the reference matches that online
- YEAR (The year of the reference): Ensure that the reference year is correct and is a valid year.

# Reference Problem Types
- CORRECT: The reference field is correct.
- MISSING: The reference field is missing.
- INCORRECT: The reference field is incorrect.
- OTHER: The reference field is other.

# Output Requirements
- For the validation result, provide the category, current value, suggested value, and problem type. If the suggested value is the same as the current value, set the problem type to CORRECT.
- If all the fields in the reference item validation are correct, set valid_reference to True.
- If any of the fields in the reference item validation are incorrect, set the valid_reference to False.
- If the reference is not valid, set the suggested action to a single-sentence action to take to fix the reference. Should be a summary of the suggested changes to make the reference valid.

Guidelines for checking the reference fields:
- For publisher, abbreviations should be considered equivalent to the full name.
- For author lists, first and last names should both be validated if they are present within the reference. If last name and first initial are present then those strings should be validated. Abbreviating remaining authors as "et al." is valid.
- For title, upper and lower case lettering is unimportant to validation (e.g., "The Title" and "the title" are considered the same title).
- For determining the title of online articles linked to PDF documents, use the title within the PDF document if available. If not, use the title of the online article.
---

# NOTE:
When generating responses, remove or replace all internal citation tokens such as turn1search0, turn2search3, or similar. Do not display raw reference IDs or metadata markers in the final text. Return clean, human-readable output only.

---

I'm going to give you the reference to validate in my next message.
"""
)


class ReferenceValidatorAgent(DirectOpenAIAgent):
    name = "Reference Validator"
    description = "Validate a list of references in a document, by searching for their online presence."
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = BibliographyItemValidation

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
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
