"""
Inference Validator V2 Agent

Analyzes full documents for inferential errors. Each finding includes the key
sentence, argument analysis, and suggested action. Ported from long_inference_checker.
"""

from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent

import logging

logger = logging.getLogger(__name__)

# for per validator testing
verbose = False

# =========================
#  Pydantic data contracts
# =========================


class InferenceAnalysis(BaseModel):
    """The result of the inference check."""

    model_config = ConfigDict(extra="forbid")

    key_sentence: str = Field(
        description="The key sentence that contains the incorrect inference, conclusion, or argument. Should be a direct quote from the text."
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


class InferenceResultResponse(BaseModel):
    """Response containing the result of the inference check."""

    model_config = ConfigDict(extra="forbid")

    results: list[InferenceAnalysis] = Field(
        description="The result of the inference check"
    )


# =========================
#  Prompt Template
# =========================


_inference_checker_prompt = ChatPromptTemplate.from_template(
    """
## Task
You are an expert in evaluating the validity of logical reasoning. Your task is to analyze the provided document and identify any inferences that are logically invalid. If they are invalid, identify the inferential errors - conclusions that are drawn but not logically supported by the premises or which have logical fallacies in the reasoning.

For each inference you identify, provide:
1. **key_sentence**: The key sentence that contains the incorrect inference, conclusion, or argument. Should be a direct quote from the text.
2. **inference_validity**: Whether the inference is valid or not.
3. **short_form_argument_analysis**: A concise analysis of what is wrong with the inference. In only TWO sentences.
4. **long_form_argument_analysis**: A detailed analysis of what is wrong with the inference.
5. **suggested_action**: A suggested action to take to correct the wrong inference. In only TWO sentences.

## Instructions
- Analyze the text carefully for logical fallacies, unsupported conclusions, or faulty reasoning
- If the text contains valid inferences with no errors, explain why they are valid
- Focus on identifying actual inferential errors, not just weak arguments
- Be precise in identifying the specific inference being made

## Text to Analyze
```
{text}
```
"""
)


# =========================
#  Agent Implementation
# =========================


class InferenceValidatorV2Agent(LangChainAgent):
    """Agent that detects inferential errors in full documents."""

    name = "Inference Validator V2"
    description = "Detect inferential errors in full documents"
    model = gpt_5_mini_model
    temperature = 0.2
    output_schema = InferenceResultResponse
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> InferenceResultResponse:
        messages = _inference_checker_prompt.format_messages(**prompt_kwargs)
        structured = await self.llm.ainvoke(messages, config=config)

        if verbose:
            n = len(structured.results)
            print(f"InferenceValidatorV2: {n} inference(s) found")
            for i, r in enumerate(structured.results, 1):
                print(
                    f"  [{i}] validity={r.inference_validity} key_sentence={r.key_sentence[:60] + '...' if len(r.key_sentence) > 60 else r.key_sentence}"
                )
            run_index = (config or {}).get("run_index", "?")
            print(
                f"InferenceValidatorV2 run {run_index}: {len(structured.results)} inference(s)"
            )

        return structured
