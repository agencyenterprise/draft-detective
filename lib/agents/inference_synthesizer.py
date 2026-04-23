"""
Inference Synthesizer Agent

Consolidates three inference validator runs: merge duplicate findings,
re-evaluate, and assign severity. Matches logic from multiple_inference_checker.
"""

from typing import Optional, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.models import SeverityEnum


# =========================
#  Pydantic data contracts
# =========================


class ConsolidatedInferenceAnalysis(BaseModel):
    """The consolidated result of the inference check."""

    model_config = ConfigDict(extra="forbid")

    key_sentence: str = Field(
        description="The key sentence that contains the incorrect inference, conclusion, or argument. Should be a direct quote from the text."
    )

    severity: SeverityEnum = Field(
        description="The severity level of the inference analysis. HIGH if the inference problem leads the conclusion to be completely invalid. MEDIUM if the inference problem weakens the justification for the conclusion. LOW if the inference problem is a minor/tangential issue that does not significantly weaken the justification for the conclusion. NONE if the inference is valid and correct."
    )

    inference_validity: bool = Field(
        description="Whether the inference is valid or not."
    )

    short_form_argument_analysis: str = Field(
        description="A concise analysis what is wrong with the inference. In only TWO sentences."
    )

    long_form_argument_analysis: str = Field(
        description="A detailed analysis what is wrong with the inference."
    )

    suggested_action: str = Field(
        description="A suggested action to take to correct the wrong inference. In only TWO sentences."
    )


class ConsolidatedInferenceResultResponse(BaseModel):
    """Response containing the consolidated result of the inference check."""

    model_config = ConfigDict(extra="forbid")

    results: list[ConsolidatedInferenceAnalysis] = Field(
        description="The result of the inference check"
    )


# =========================
#  Prompt Template
# =========================


_COLLATOR_PROMPT = ChatPromptTemplate.from_template(
    """
## Task
You are given three independent inference-check results for the same document in addition to the full document. Your task is to re-evaluate the inference check results and consolidate them into a single, double-checked list of inference analyses

## Instructions
1. Merge findings that refer to the same inference (same key sentence or same underlying issue). Treat paraphrased or semantically equivalent key sentences as the same finding.
2. Re-evaluate the merged findings to determine if they are valid and should be kept as inference analyses for the document. Analyses that are determined as invalid should be dropped as problems. Analyses that are determined to be valid should be kept as inference analyses for the document.
3. Determine the severity level of the inference analysis. HIGH if the inference problem leads the conclusion to be completely invalid. MEDIUM if the inference problem weakens the justification for the conclusion. LOW if the inference problem is a minor/tangential issue that does not significantly weaken the justification for the conclusion. NONE if the inference is valid and correct.
4. Output a single list in the exact schema: each item has key_sentence, inference_validity, severity, short_form_argument_analysis, long_form_argument_analysis, suggested_action. Keep analyses concise (e.g., two sentences where specified).
5. If all three runs found no issues, output an empty list. Do not invent findings.

When merging findings, ask yourself the following questions:
- Are the findings referring to the same inference/key sentence?
- Do the findings describe the same underlying problem with a passage/sentence?

When re-evaluating inferences, ask yourself the following questions:
- On a second comparison between document and inference analysis, does the inference analysis truly identify a problem or is it a false positive?
- Given the repetition of inference problems found across multiple runs, is this plausibly a serious issue?

For each retained inference you identify, provide:
1. **key_sentence**: The key sentence that contains the incorrect inference, conclusion, or argument. Should be a direct quote from the text.
2. **inference_validity**: Whether the inference is valid or not.
3. **severity**: How severe the inference problem is.
4. **short_form_argument_analysis**: A concise analysis of what is wrong with the inference. In only TWO sentences.
5. **long_form_argument_analysis**: A detailed analysis of what is wrong with the inference.
6. **suggested_action**: A suggested action to take to correct the wrong inference. In only TWO sentences.

# Agent Inputs

## Full Document

```
{full_document}
```

## Run 1
```json
{run1_json}
```

## Run 2
```json
{run2_json}
```

## Run 3
```json
{run3_json}
```
Produce the consolidated InferenceResultResponse (a single "results" array of inference analyses).
"""
)


# =========================
#  Agent Implementation
# =========================


class InferenceSynthesizerAgent(LangChainAgent):
    """Agent that consolidates three inference validator runs: merge, re-evaluate, assign severity."""

    name = "Inference Synthesizer"
    description = "Consolidate three inference check runs: merge, disambiguate, and rank by severity"
    model = gpt_5_mini_model
    temperature = 0.2
    output_schema = ConsolidatedInferenceResultResponse
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> ConsolidatedInferenceResultResponse:
        messages = _COLLATOR_PROMPT.format_messages(**prompt_kwargs)
        return cast(
            ConsolidatedInferenceResultResponse,
            await self.llm.ainvoke(messages, config=config),
        )
