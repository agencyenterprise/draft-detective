"""
Advocacy and Tone Verifier Agent

Verifies procedurally-flagged sentences using LLM to confirm and explain
trigger words, advocacy language, or subjective tone issues.
"""

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.advocacy_tone.state import AdvocacyToneCheckType


class AdvocacyToneVerificationResponse(BaseModel):
    """Response from LLM verification."""

    confirmed: bool = Field(description="Whether the issue is confirmed after review")
    explanation: str = Field(
        description="Brief explanation (1-2 sentences) of the finding"
    )
    word_positions: List[int] = Field(
        default_factory=list,
        description="1-indexed positions of problematic words in the sentence",
    )


_verification_prompt = ChatPromptTemplate.from_template(
    """You are an impartial text analyzer checking research reports for language issues.

## Task
Analyze the target sentence and determine if it contains {check_type_description}.

## Definitions
{definitions}

## Context (surrounding sentences)
{context}

## Target Sentence to Analyze
{target_sentence}

## Target Sentence Tokenized (positions start at 1)
{tokenized_sentence}

## Instructions
1. Only analyze the TARGET sentence (use context for understanding only)
2. If the issue is confirmed (confirmed = true):
   - Return the 1-indexed word positions causing the issue
   - Provide a clear 1-2 sentence explanation
3. If the issue is NOT confirmed (confirmed = false):
   - Return empty positions list
   - Briefly explain why this is acceptable

Important: Simple, factual mentions of legal terms or policies in an objective context should NOT be flagged.
"""
)

CHECK_TYPE_CONFIGS = {
    AdvocacyToneCheckType.TRIGGER_WORDS: {
        "description": "legally sensitive language that requires special review before publication",
        "definitions": """Legally Sensitive Language: Words or phrases that could imply legal risk, 
liability, compliance, guarantees, obligations, punishments, or contractual commitments.

Categories and examples include (but are not limited to):
- Liability / Responsibility: liable, indemnify, responsible for damages, binding
- Compliance / Legal Duty: must comply, mandatory, prohibited, illegal, unlawful
- Enforcement / Punishment: penalty, punishable, fine, prosecution
- Contractual Terms: agreement, terms and conditions, obligation

Important exceptions to NOT flag:
- Simple usage of "laws" in physics or natural sciences context
- "Policy" in "policy researcher" or "policy research" context
- Objective, factual descriptions like "the policy states" or "according to the law"
- Academic discussion of legal concepts without advocacy""",
    },
    AdvocacyToneCheckType.ADVOCACY_LANGUAGE: {
        "description": "normative advocacy that should be minimized in objective research",
        "definitions": """Advocacy Language: Promotes a position, expresses approval/disapproval, 
or calls for action without substantial facts or evidence. Neutral language is factual, 
descriptive, or analytical.

Examples of advocacy patterns to flag:
- Strong recommendations: "we should", "we must", "must ensure", "have to", "need to"
- Imperative framing: "it is essential that", "it is imperative that", "it is our duty to"
- Calls to action: "recommend that", "call for", "urge X to", "advocate for", "lobby for"
- Strong evaluative: "critical to", "vital to", "of utmost importance", "unacceptable that"
- Policy advocacy: "policy should", "should be adopted", "should be implemented"

Important exceptions to NOT flag:
- Recommendations backed by evidence with appropriate qualifiers
- Standard academic conclusions section language
- Hedged suggestions (e.g., "one possible approach might be")""",
    },
    AdvocacyToneCheckType.SUBJECTIVE_TONE: {
        "description": "strong subjectivity not backed by facts or research",
        "definitions": """Subjective Tone: Judgments, opinions, evaluations, or emotionally loaded 
language that goes beyond neutral research reporting. Signals bias or advocacy instead of 
objective description.

Categories of subjective language to flag:
- Positive/Negative evaluations: excellent, terrible, remarkable, inadequate, wonderful, awful
- Emotive language: alarming, shocking, tragic, promising, catastrophic, outrageous
- Persuasive/certainty cues: clearly, obviously, undoubtedly, certainly, definitely, absolutely
- Overgeneralizations: everyone knows, always, never, unquestionably, indisputably

Objective language (do NOT flag) is factual, descriptive, measurable, and backed by data:
- "GDP grew by 3.2%"
- "The survey included 200 respondents"
- "The sample was drawn from three districts"
- Evidence-backed evaluations with citations""",
    },
}


class AdvocacyToneVerifierAgent(LangChainAgent):
    """Agent that verifies procedurally-flagged advocacy/tone issues."""

    name = "Advocacy Tone Verifier"
    description = "Verify and explain advocacy/tone issues in text"
    model = gpt_5_mini_model
    temperature = 0.2
    output_schema = AdvocacyToneVerificationResponse

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> AdvocacyToneVerificationResponse:
        """Invoke the agent to verify a flagged sentence.

        Expected prompt_kwargs:
            - check_type: AdvocacyToneCheckType
            - target_sentence: str
            - context: str (surrounding sentences)
        """
        check_type = prompt_kwargs["check_type"]
        check_config = CHECK_TYPE_CONFIGS[check_type]

        # Tokenize the target sentence for position reference
        words = prompt_kwargs["target_sentence"].split()
        tokenized = [{"position": i + 1, "word": w} for i, w in enumerate(words)]

        formatted_kwargs = {
            "check_type_description": check_config["description"],
            "definitions": check_config["definitions"],
            "context": prompt_kwargs["context"],
            "target_sentence": prompt_kwargs["target_sentence"],
            "tokenized_sentence": str(tokenized),
        }

        messages = _verification_prompt.format_messages(**formatted_kwargs)
        result = await self.llm.ainvoke(messages, config=config)

        # Convert 1-indexed positions to 0-indexed for storage
        if result.word_positions:
            result.word_positions = [p - 1 for p in result.word_positions if p > 0]

        return result
