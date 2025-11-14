from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from typing import Optional, List
from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import DEFAULT_LLM_TIMEOUT, AgentProtocol


class Claim(BaseModel):
    """A single factual claim with verification properties."""

    text: str = Field(
        description="The relevant part of the text within the chunk of text that is being decomposed into claims."
    )

    claim: str = Field(description="The claim made in the text")

    rationale: str = Field(
        description="The rationale for why you think the chunk of text implies this claim"
    )


class ClaimResponse(BaseModel):
    claims: list[Claim] = Field(
        description="A list of claims made in the chunk of text"
    )
    rationale: str = Field(
        description="Overall rationale for why you think the chunk of text implies these claims"
    )


# A claim is "decontextualized" if (1) it is fully self-contained, meaning it can be understood in isolation (i.e., without the context of the full document), AND (2) its meaning in isolation matches its meaning when interpreted alongside the paragraph and the full document and other claims. The claims should also be the simplest possible discrete units of information.

#
## Guidelines
# - Do NOT repeat the same claim in the list of claims. I repeat: It is extremely important that you do not repeat the same claim in the list of claims.
# - Only write a claim if the the statement expresses an assertion or a proposition. Statements like "The document is about the domain of the document" are not claims and should not be included in the list of claims.
# - If a sentence has multiple adjectives/modifiers describing the same entity, you should include all those adjectives/modifiers in the same claim.
# For example, the sentence "A, B, and C are all good at X" should be decomposed into the claims "A, B, and C are all good at X", and the sentece "X affects C and D differently" should be decomposed into the claims "X affects C and D differently".

_claim_extractor_prompt_claimify = ChatPromptTemplate.from_template(
    """

### Agent Setup and Terms
You are an assistant for a group of fact-checkers. You will be given a paragraph from a document and a chunk of text (typically a sentence or a few sentences) from that paragraph, and your task is to extract all the claims from the chunk of text. 

Claim (definition): An assertion or proposition that is made within a chunk of text. Grammatically, a sentence that expresses a claim is a declarative sentence and thus contains a verb. 

True Examples of Claims:
- "Quantum gravity is a theory that combines quantum mechanics and general relativity" (Statement/description of a theory)
- "Developments in neural networks has accelerated the economic divide between first and third world countries" (Statement/description of a fact)
- "The United States has the highest GDP in the world" (Statement/description of a fact)

Non-Examples of Claims:
- "The Space Time Approach to Quantum Gravity" (This is a title of a paper, not a claim)
- "Johnson, J. (2024) Economic consequences of developing neural networks" (This is a reference, not a claim)


### Task
Your task is to identify all specific propositions in the sentence and ensure that each proposition is decontextualized. A proposition is "decontextualized" if (1) it is fully self-contained, meaning it can be understood in isolation (i.e., without the question, the context, and the other propositions), AND (2) its meaning in isolation matches its meaning when interpreted alongside the question, the context, and the other propositions. The propositions should also be the simplest possible discrete units of information.

Note the following rules:
- If the chunk of text is a bibliographic entry (usually found in references or bibliography sections, indicated by headings like "References", "Bibliography", "Works Cited"), do not consider it as having claims.
- Sometimes a specific claim is buried in a sentence that is mostly generic or unverifiable. For example, "John's notable research on neural networks demonstrates the power of innovation" contains the specific claim "John has research on neural networks". Another example is "TurboCorp exemplifies the positive effects that prioritizing ethical considerations over profit can have on innovation" where the specific claim is "TurboCorp prioritizes ethical considerations over profit".
- Do NOT repeat the same claim in the list of claims.
- Do NOT use any external knowledge beyond what is stated in the paragraph and chunk of text.

Each proposition must be:
- Specific: It should refer to particular entities, events, or relationships
- Decontextualized: It should be understandable without additional context

Important rules:
- If a sentence has multiple adjectives/modifiers describing the same entity, you should include all those adjectives/modifiers in the same claim. 
- Do NOT repeat the same claim in the list of claims.
- Do NOT use any external knowledge beyond what is stated in the paragraph and chunk of text
- Each fact-checker will only have access to one claim - they will not have access to the paragraph and other claims
- Do not classify something as a claim if it cannot be decontextualized (i.e., it cannot be understood or verified in isolation without additional context from the document)
- If there are no specific claims in the chunk of text, return an empty list of claims.

### Output Structure

For the final claims, you must create structured objects with:
- rationale: The rationale for why you think the chunk of text implies this list of claims
- list of claims: The list of claims made in the chunk of text

Within the list of claims, you must include the following information for each claim:
- text: The relevant part of the text within the chunk of text that implies the claim
- claim: The claim text
- rationale: The rationale for why you think the chunk of text implies this claim


### Agent Inputs

## Domain context (context about the domain of the document)
{domain_context}

## Audience context (context about the audience of the document)
{audience_context}

## The paragraph of the original document that contains the chunk of text that we want to analyze
```
{paragraph}
```

## The chunk of text to extract claims from
```
{chunk}
```
"""
)


class ClaimExtractorAgent(AgentProtocol):
    name = "Claim Extractor"
    description = "Extract claims from a chunk of text"

    def __init__(self):
        self.llm = init_chat_model(
            gpt_5_mini_model.model_name,
            temperature=0.5,
            timeout=DEFAULT_LLM_TIMEOUT,
        ).with_structured_output(ClaimResponse)

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> ClaimResponse:
        messages = _claim_extractor_prompt_claimify.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)


claim_extractor_agent = ClaimExtractorAgent()


# Interactive testing script
if __name__ == "__main__":
    import asyncio
    import json
    from lib.agents.formatting_utils import (
        format_domain_context,
        format_audience_context,
    )

    # Test examples from claim_extractor.yaml dataset
    TEST_EXAMPLES = [
        # index 0
        {
            "name": "Multiple claims with citations",
            "full_document": """# Effects of Widgets on System Performance

This study explores how widgets impact overall gadget performance metrics.

## Introduction

Widgets have been widely adopted across industries. Prior work such as Smith (2020) and Doe and Roe (2019) provide useful background/insights. In this article, we will review what some of the other works in the field, including (Smith, 2017) have found in this domain.

## Methods

We conducted experiments using standard gizmo benchmarks.

## Results

Widgets improved throughput but increased latency under certain configurations. Of note, cellphones have a positive impact on the user's writing proficiency in most countries (Smith, 2017), making them one of the best widgets out there.

Cellphones are good for the brain, as has been found before.

## Discussion

Findings align with prior work.

## References

1. Smith, J. (2020). The Effects of Widgets on Gadgets. Journal of Widgetry.
2. Doe, A.; Roe, B. (2019). A Comprehensive Study of Gizmos. Proceedings of Gizmo Conf.
3. Smith, A.; Anderson, T. (2017), A Study of The Effect of Cellphones on Writing Ability. Journal of Big Tech.""",
            "paragraph": "Widgets have been widely adopted across industries. Prior work such as Smith (2020) and Doe and Roe (2019) provide useful background/insights. In this article, we will review what some of the other works in the field, including (Smith, 2017) have found in this domain.",
            "chunk": "Prior work such as Smith (2020) and Doe and Roe (2019) provide useful background/insights.",
            "domain": None,
            "target_audience": None,
        },
        # index 1
        {
            "name": "Multiple claims including widget claim",
            "full_document": """# Effects of Widgets on System Performance

This study explores how widgets impact overall gadget performance metrics.

## Introduction

Widgets have been widely adopted across industries. Prior work such as Smith (2020) and Doe and Roe (2019) provide useful background/insights. In this article, we will review what some of the other works in the field, including (Smith, 2017) have found in this domain.

## Methods

We conducted experiments using standard gizmo benchmarks.

## Results

Widgets improved throughput but increased latency under certain configurations. Of note, cellphones have a positive impact on the user's writing proficiency in most countries (Smith, 2017), making them one of the best widgets out there.

Cellphones are good for the brain, as has been found before.

## Discussion

Findings align with prior work.

## References

1. Smith, J. (2020). The Effects of Widgets on Gadgets. Journal of Widgetry.
2. Doe, A.; Roe, B. (2019). A Comprehensive Study of Gizmos. Proceedings of Gizmo Conf.
3. Smith, A.; Anderson, T. (2017), A Study of The Effect of Cellphones on Writing Ability. Journal of Big Tech.""",
            "paragraph": "Widgets improved throughput but increased latency under certain configurations. Of note, cellphones have a positive impact on the user's writing proficiency in most countries (Smith, 2017), making them one of the best widgets out there.",
            "chunk": "Of note, cellphones have a positive impact on the user's writing proficiency in most countries (Smith, 2017), making them one of the best widgets out there.",
            "domain": None,
            "target_audience": None,
        },
        # index 2
        {
            "name": "No claims - header only",
            "full_document": """# Effects of Widgets on System Performance

This study explores how widgets impact overall gadget performance metrics.

## Introduction

Widgets have been widely adopted across industries. Prior work such as Smith (2020) and Doe and Roe (2019) provide useful background/insights. In this article, we will review what some of the other works in the field, including (Smith, 2017) have found in this domain.""",
            "paragraph": "# Effects of Widgets on System Performance",
            "chunk": "# Effects of Widgets on System Performance",
            "domain": None,
            "target_audience": None,
        },
        # index 3
        {
            "name": "Criminal justice system purpose",
            "full_document": """## Introduction

The criminal justice system in the United States is intended to deter, punish, and reform individuals who violate the norms of good order and mutual respect that are enshrined in law. The associated legal structures were developed, for the most part, before the development of such information technologies as the postal service, telegraph, and telephone systems. With the development of personal computers connected by the internet, much larger portions of economic and interpersonal interactions have moved online, as has criminal activity. This shift of activity into digital spaces has presented a multitude of difficulties, as well as opportunities, for criminal justice practitioners (Goodison, Davis, and Jackson, 2015; Tanneeru, 2009; Vermeer, Woods, and Jackson, 2018).""",
            "paragraph": "The criminal justice system in the United States is intended to deter, punish, and reform individuals who violate the norms of good order and mutual respect that are enshrined in law. The associated legal structures were developed, for the most part, before the development of such information technologies as the postal service, telegraph, and telephone systems.",
            "chunk": "The criminal justice system in the United States is intended to deter, punish, and reform individuals who violate the norms of good order and mutual respect that are enshrined in law.",
            "domain": None,
            "target_audience": None,
        },
        # index 4
        {
            "name": "Digital shift of activities",
            "full_document": """## Introduction

The criminal justice system in the United States is intended to deter, punish, and reform individuals who violate the norms of good order and mutual respect that are enshrined in law. The associated legal structures were developed, for the most part, before the development of such information technologies as the postal service, telegraph, and telephone systems. With the development of personal computers connected by the internet, much larger portions of economic and interpersonal interactions have moved online, as has criminal activity. This shift of activity into digital spaces has presented a multitude of difficulties, as well as opportunities, for criminal justice practitioners (Goodison, Davis, and Jackson, 2015; Tanneeru, 2009; Vermeer, Woods, and Jackson, 2018).""",
            "paragraph": "With the development of personal computers connected by the internet, much larger portions of economic and interpersonal interactions have moved online, as has criminal activity.",
            "chunk": "With the development of personal computers connected by the internet, much larger portions of economic and interpersonal interactions have moved online, as has criminal activity.",
            "domain": None,
            "target_audience": None,
        },
        # index 5
        {
            "name": "AI power capacity requirement",
            "full_document": """# Assessing the United States' Net Additional AI Power Capacity by 2030

Estimating short-term increases in electricity generation and the ability to meet growth in power demand

## Chapter 1. Introduction

Anticipated growth in artificial intelligence (AI) development requires the buildout of additional power capacity at an exceptional scale and speed. There is concern that the necessary grid loads to power future AI data centers for training and inference activities may exceed the capacity of additions to the U.S. power grid.[[18]](#footnote-18) In this report, we assess potential increases in supply resources in the contiguous United States and propose a capacity metric that can be directly compared with load increases. We address the following question: What will the United States' additional power capacity be by 2030?""",
            "paragraph": "Anticipated growth in artificial intelligence (AI) development requires the buildout of additional power capacity at an exceptional scale and speed. There is concern that the necessary grid loads to power future AI data centers for training and inference activities may exceed the capacity of additions to the U.S. power grid.[[18]](#footnote-18) In this report, we assess potential increases in supply resources in the contiguous United States and propose a capacity metric that can be directly compared with load increases.",
            "chunk": "Anticipated growth in artificial intelligence (AI) development requires the buildout of additional power capacity at an exceptional scale and speed.",
            "domain": None,
            "target_audience": None,
        },
        # index 6
        {
            "name": "Reference entry - no claims expected",
            "full_document": """## References

Caldwell, Leslie R., "Assistant Attorney General Leslie R. Caldwell Delivers Remarks at the Securities Enforcement Forum West Conference," U.S. Department of Justice, May 12, 2016.

Hill, Jonah Force, "Problematic Alternatives: MLAT Reform for the Digital Age," *Harvard Law School National Security Journal*, January 28, 2015.""",
            "paragraph": "Caldwell, Leslie R., 'Assistant Attorney General Leslie R. Caldwell Delivers Remarks at the Securities Enforcement Forum West Conference,' U.S. Department of Justice, May 12, 2016.",
            "chunk": "Caldwell, Leslie R., 'Assistant Attorney General Leslie R. Caldwell Delivers Remarks at the Securities Enforcement Forum West Conference,' U.S. Department of Justice, May 12, 2016.",
            "domain": None,
            "target_audience": None,
        },
        # index 7
        {
            "name": "Machine learning improves image classification",
            "full_document": """# Advances in Machine Learning for Image Classification

Machine learning techniques have revolutionized the field of image classification over the past decade, with convolutional Neural Networks (CNNs) enabling significant improvements over previous approaches, and researchers like Krizhevsky et al. (2012) reporting unprecedented performance on the ImageNet dataset, which has spurred advances in both academic and industrial applications.

## State of the Art

CNNs, such as AlexNet, VGGNet, and ResNet, have become standard tools for image recognition tasks. According to recent benchmarks, deep networks often outperform traditional feature engineering methods.

## Challenges

Despite their successes, deep learning models often require large labeled datasets and significant computational resources.

## Conclusion

Machine learning will likely continue to drive progress in automated visual understanding.""",
            "paragraph": "Machine learning techniques have revolutionized the field of image classification over the past decade. Convolutional Neural Networks (CNNs) have enabled significant improvements over previous approaches. Researchers like Krizhevsky et al. (2012) reported unprecedented performance on the ImageNet dataset, spurring advances in both academic and industrial applications.",
            "chunk": "Machine learning techniques have revolutionized the field of image classification over the past decade, with convolutional Neural Networks (CNNs) enabling significant improvements over previous approaches, and researchers like Krizhevsky et al. (2012) reporting unprecedented performance on the ImageNet dataset, which has spurred advances in both academic and industrial applications.",
            "domain": "Machine Learning",
            "target_audience": "Computer vision researchers",
        },
    ]

    async def test_claim_extraction(example: dict):
        """Test claim extraction on a text section from the example."""

        # Format context
        domain_context = format_domain_context(example.get("domain"))
        audience_context = format_audience_context(example.get("target_audience"))

        # Prepare prompt kwargs
        prompt_kwargs = {
            "paragraph": example["paragraph"].strip(),
            "chunk": example["chunk"].strip(),
            "domain_context": domain_context,
            "audience_context": audience_context,
        }

        print("=" * 80)
        print(f"Testing: {example['name']}")
        print("=" * 80)
        print(f"\nChunk:\n{example['chunk'].strip()}\n")
        print("=" * 80)
        print("\nExtracting claims...\n")

        # Run claim extraction
        result = await claim_extractor_agent.ainvoke(prompt_kwargs)

        # Display results
        print("=" * 80)
        print("EXTRACTION RESULTS")
        print("=" * 80)
        print(f"\nOverall Rationale:\n{result.rationale}\n")
        print(f"Number of Claims Extracted: {len(result.claims)}\n")

        for i, claim in enumerate(result.claims, 1):
            print(f"--- Claim {i} ---")
            print(f"Text: {claim.text}")
            print(f"Claim: {claim.claim}")
            print(f"Rationale: {claim.rationale}")
            print()

        # Also print as JSON for easy inspection
        # print("=" * 80)
        # print("JSON Output:")
        # print("=" * 80)
        # print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
        # print("\n" + "=" * 80 + "\n")

    async def run_all_examples():
        """Run all test examples."""
        for example in TEST_EXAMPLES:
            await test_claim_extraction(example)

    async def run_single_example(index: int = 0):
        """Run a single test example by index."""
        if 0 <= index < len(TEST_EXAMPLES):
            await test_claim_extraction(TEST_EXAMPLES[index])
        else:
            print(f"Invalid index. Choose between 0 and {len(TEST_EXAMPLES) - 1}")

    # Run the tests
    # Change this to run a specific example or all examples
    # Examples: 0=Multiple claims with citations, 1=Multiple claims including widget, etc.
    EXAMPLE_INDEX = 0  # Change this to test different examples (0-7)

    if EXAMPLE_INDEX is None:
        asyncio.run(run_all_examples())
    else:
        asyncio.run(run_single_example(EXAMPLE_INDEX))
