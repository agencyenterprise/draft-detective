# %%
# reference validator agent
"""
Validates the list of references in a document, by searching for their online presence.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_2_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


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
    IDENTIFIER = "identifier"


class BibliographyFieldValidation(BaseModel):
    category: FieldCategory = Field(description="Category of the reference.")
    current_value: str = Field(description="Current value of the reference.")
    suggested_value: str = Field(description="Suggested value of the reference.")
    problem_type: FieldProblemType = Field(
        description="Problem type of the reference. Must be CORRECT if the only differences are capitalization or minor punctuation."
    )


class ReferenceValidationFinalResult(str, Enum):
    VALID = "valid"
    FOUND_WITH_INCONSISTENCIES = "found_with_inconsistencies"
    NOT_FOUND = "not_found"


class BibliographyItemValidation(BaseModel):
    original_reference: str = Field(description="Original bibliographic item text.")
    final_result: ReferenceValidationFinalResult = Field(
        description="Overall validation outcome: 'valid' if found online with no inconsistencies, "
        "'found_with_inconsistencies' if found but some fields need correction, "
        "'not_found' if the reference has no online presence or appears fabricated."
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


SYSTEM_PROMPT = """Validate a single bibliographic reference by searching for it online and checking its accuracy.

You will receive one reference item from a document's bibliography. Use web search to locate the cited work, then verify each field against the authoritative source you find.

# Validation procedure

1. Search for the reference online to find a matching legitimate source.
2. For each field (author, title, publisher, year, identifier), compare the reference's value against what you found online.
3. Determine whether the reference is valid overall.

# Field validation rules

- **Author**: Verify all listed authors exist and names are spelled correctly. Both "first last" and "last, F." formats are acceptable. "et al." is valid for truncating author lists.
- **Title**: Verify the title matches the source **in wording only**. Capitalization and minor punctuation differences are NEVER errors. Example: current value "Webvoyager: Building an end-to-end web agent with large multimodal models." vs. authoritative "WebVoyager: Building an End-to-End Web Agent with Large Multimodal Models" → mark CORRECT because the words are the same. For PDF-linked articles, prefer the title inside the PDF over the webpage title.
- **Publisher**: Verify the publisher matches. Abbreviations are equivalent to full names (e.g., "ACM" = "Association for Computing Machinery"). Capitalization differences are not errors.
- **Year**: Verify the publication year is correct.
- **Identifier**: Verify any persistent identifier such as a DOI, arXiv ID, ISBN, ISSN, or similar. If the reference includes one, check that it resolves to the correct work. If the reference omits an identifier but one exists for the work, mark as MISSING and provide the correct identifier as the suggested value. If no identifier exists for the work, mark as CORRECT with an empty current_value and suggested_value.

# Formatting policy

Accept any broadly recognizable citation style (APA, Chicago, MLA, IEEE, etc.). Do not flag minor stylistic differences such as capitalization, punctuation choice, field ordering, or comma vs. period usage. Capitalization variants (title case, sentence case, all caps) and minor punctuation differences (trailing periods, commas vs. semicolons, hyphens vs. dashes) must be treated as equivalent. Page ranges (e.g., "pp. 1-10") should be ignored for validation purposes — do not flag them as incorrect or missing. Focus exclusively on content accuracy, not style conformance.

# Bare URL references

A reference consisting solely of a URL with no bibliographic metadata is always invalid. Mark all five fields as MISSING and reconstruct the full citation from the URL's content in updated_reference.

# Output logic

- **Capitalization/punctuation check (apply first)**: Before marking any field INCORRECT, ask: "If I ignore uppercase/lowercase differences and minor punctuation (periods, commas, hyphens, colons), do the two values convey the same words?" If yes → the field is CORRECT.
- Set problem_type to CORRECT when the field's value matches the authoritative source in wording (suggested_value equals current_value ignoring case and punctuation).
- Set problem_type to MISSING when the field is absent from the reference.
- Set problem_type to INCORRECT only when the field contains different words, different names, wrong numbers, or factually wrong information.
- Set final_result to one of: `valid`, `found_with_inconsistencies`, or `not_found`:
  - `valid`: the reference was found online and any differences are trivial or non-actionable. Use `valid` even when minor fields are technically missing or slightly off, as long as the reference clearly identifies the correct work. Examples of trivial differences that should remain `valid`: a missing DOI when an arXiv ID (or other identifier) is already present, minor author name format variations (initials vs. full first names), a missing publisher when the venue is obvious, or slight title wording differences that don't change meaning.
  - `found_with_inconsistencies`: the reference was found online but has **substantial** errors that would mislead a reader or make the work hard to locate — e.g., wrong author names, a factually incorrect title, wrong publication year, or a completely missing title/author. Reserve this status for differences that genuinely need to be corrected.
  - `not_found`: the reference could not be located online, or the identifiers/URLs/authors appear fabricated or point to a different work.
- When invalid, write a single-sentence suggested_action summarizing what to fix.
- When invalid and a matching source was found, provide updated_reference with corrections applied, preserving the original citation format. When valid, or when no matching source could be found online, set updated_reference to null.

# Response hygiene

Never include internal search tokens (e.g., turn0search0, turn2search3) or raw metadata markers in any output field. All text must be clean and human-readable.

---

The reference to validate will be provided in the next message."""


class ReferenceValidatorAgent(LangChainAgent):
    name = "Reference Validator"
    description = "Validate a list of references in a document, by searching for their online presence."
    model = gpt_5_2_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> BibliographyItemValidation:
        agent = create_agent(
            self.llm,
            [{"type": "web_search"}],
            system_prompt=SYSTEM_PROMPT,
            context_schema=ContextSchema,
            response_format=BibliographyItemValidation,
        )

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt_kwargs["reference"]}]},
            config=config,
            context=self.context,
        )

        return result["structured_response"]
