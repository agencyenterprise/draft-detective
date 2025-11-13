# %%
# reference validator agent
"""
Validates the list of references in a document, by searching for their online presence.
"""
from __future__ import annotations


from enum import Enum


from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from typing import List
from lib.services.openai import (
    get_openai_client,
    wait_for_response,
    ensure_structured_output_response,
)
from lib.config.llm_models import gpt_5_model
from lib.models.agent import AgentProtocol
from lib.agents.reference_extractor import (
    BibliographyItem,
)


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
    original_reference: BibliographyItem = Field(
        description="Original bibliographic item text."
    )
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


class BibliographyValidationResponse(BaseModel):
    reference_validations: List[BibliographyItemValidation] = Field(
        description="List of reference item validations."
    )


_reference_validator_prompt = PromptTemplate.from_template(
    """
You are an expert reference validator. Your task is to validate the list of references in a document
by ensuring there is online presence from a legitimate source from each one.

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
- Provide a list of reference item validations.
- For each reference item validation, provide the category, current value, suggested value, and problem type. If the suggested value is the same as the current value, set the problem type to CORRECT.
- If all the fields in the reference item validation are correct, set valid_reference to True.
- If any of the fields in the reference item validation are incorrect, set the valid_reference to False.
- If the reference is not valid, set the suggested action to a single-sentence action to take to fix the reference. Should be a summary of the suggested changes to make the reference valid.

Guidelines for checking the reference fields:
- For publisher, abbreviations should be considered equivalent to the full name.
- For author lists, first and last names should be valid if they are both present. If last name, and first initial are present then those should be valid. Abbreviating remaining authors as "et al." is valid.

---

# NOTE:
When generating responses, remove or replace all internal citation tokens such as turn1search0, turn2search3, or similar. Do not display raw reference IDs or metadata markers in the final text. Return clean, human-readable output only.

Return one JSON object matching the schema exactly.


## The list of references to validate
{references}
"""
)


class ReferenceValidatorAgent(AgentProtocol):
    name: str = "Reference Validator"
    description: str = (
        "Validate a list of references in a document, by searching for their online presence."
    )

    def __init__(self):
        self.client = get_openai_client()

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> BibliographyValidationResponse:
        prompt = _reference_validator_prompt.invoke(prompt_kwargs)
        input = [{"role": "user", "content": prompt.text}]

        response = await self.client.responses.parse(
            model=gpt_5_model.name,
            tools=[{"type": "web_search"}],
            max_tool_calls=20,
            reasoning={
                "effort": "low",  # "minimal", "low", "medium", "high"
                "summary": "auto",
            },
            text_format=BibliographyValidationResponse,
            background=True,
            input=input,
        )

        response = await wait_for_response(
            self.client, response, poll_interval_seconds=10
        )
        return ensure_structured_output_response(
            response, BibliographyValidationResponse
        )


reference_validator_agent = ReferenceValidatorAgent()

# %%
if __name__ == "__main__":
    import asyncio

    import nest_asyncio

    nest_asyncio.apply()
    # Test cases for reference validation
    test_cases = [
        {
            "references": [
                "Daniel Furrer, Jonathan Berant, Panupong Pasupat, Don Tuggener, Mark Cieliebak, and Mark Steedman. Compositional generalization in semantic parsing: Pre-training vs. specialized architectures. In Findings of the Association for Computational Linguistics: EMNLP, 2020.",
                "Jonathan Herzig. Unlocking compositional generalization in pretrained models using intermediate representations. In EMNLP, 2021a.",
                "Jonathan Herzig and Jonathan Berant. Unlocking compositional generalization in pretrained models using intermediate representations.",
                "Jonathan Herzig and Jonathan Berant. Unlocking compositional generalization in pretrained models using intermediate representations. In EMNLP, 2021c.",
                "Takashi Ito, Brenden M. Lake, and Marco Baroni. Compositional generalization through abstract representations in human and artificial neural networks. In NeurIPS, 2022.",
            ],
        },
        {
            "references": [
                "Najoung Kim and Tal Linzen. Cogs: A compositional generalization challenge based on semantic interpretation. In NAACL, 2021.",
                "Brenden M. Lake and Marco Baroni. Generalization without systematicity: On the compositional skills of sequence-to-sequence recurrent networks. ICML, 2018.",
                "Xueguang Li, Yizhe Zhang, Xuezhe Ma, Lemao Liu, Xiang Chen, Ming Zhou, Tie-Yan Liu, and Jianfeng Gao. Compositional generalization through meta sequence-to-sequence learning. In EMNLP, 2021.",
                "Laura Ruis, Jacob Andreas, Marco Baroni, Diane Bouchacourt, and Brenden M. Lake. A benchmark for systematic generalization in grounded language understanding. In NeurIPS, 2020.",
                'Herzig, Jonathan, Peter Shaw, Ming-Wei Chang, Kelvin Guu, Panupong Pasupat, and Yuan Zhang. "Unlocking compositional generalization in pre-trained models using intermediate representations." arXiv preprint arXiv:2104.07478 (2021).',
            ],
        },
    ]

    # Run tests and compare results
    for i, test_case in enumerate(test_cases, 1):
        response = asyncio.run(reference_validator_agent.ainvoke(test_case))

        print(f"\nTest Case {i}:")
        # print(f"References: {test_case['references']}")
        for reference_item_validation in response.reference_validations:
            print(f"Original Reference: {reference_item_validation.original_reference}")
            print(
                f"Is the reference valid? {reference_item_validation.valid_reference}"
            )
            for (
                reference_field_validation
            ) in reference_item_validation.bibliography_field_validations:
                print(f"Category: {reference_field_validation.category}")
                print(f"Current Value: {reference_field_validation.current_value}")
                print(f"Suggested Value: {reference_field_validation.suggested_value}")
                print(f"Problem Type: {reference_field_validation.problem_type}")
                print("--------------------------------")
            print(f"Suggested Action: {reference_item_validation.suggested_action}")
            print(f"URL: {reference_item_validation.url}")
            print("-**********************************-")
            print()
