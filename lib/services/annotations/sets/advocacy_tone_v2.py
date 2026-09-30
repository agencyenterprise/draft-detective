"""The Advocacy & Tone annotation set; guidance paraphrases its skill for a person."""

from lib.services.annotations.set_spec import AnnotationSetSpec, should_flag_question

ADVOCACY_TONE = AnnotationSetSpec(
    slug="advocacy_tone_v2",
    title="Advocacy & Tone",
    workflow_type="advocacy_tone_v2",
    summary="Is the highlighted language neutral, as research writing should be?",
    guidance="""\
The check flags three kinds of non-neutral language:

- **Trigger words:** certainty without evidence (*obviously*, *clearly*, *undoubtedly*, *always*, *never*).
- **Advocacy language:** the author's own opinion or push presented as a finding (*we believe*, *it is clear that*), including *must*, *urgent*, *critical*, *essential* or *ensure* when they assert a position or obligation (*policymakers must act now*).
- **Subjective tone:** value judgments or emotionally loaded wording.

It leaves these alone:

- Terms of art (*critical infrastructure*, *essential services*).
- Technical requirements and methods language (*the sample must be refrigerated*, *to ensure data quality, responses were validated*).
- Descriptions or quotations of existing rules (*under the statute, agencies must report within 24 hours*).
- Claims that are hedged or backed by the evidence given.
- Anything in the authors, references, bibliography, appendix or acknowledgments sections.
""",
    questions=[should_flag_question()],
    decoy_reasons={
        "quoted_regulation": "it quotes a regulation",
        "term_of_art": "the word is part of a term of art",
        "technical_requirement": "it states a technical requirement",
        "methods_language": "it describes the study's methods",
        "existing_obligation": "it describes an obligation that already exists",
        "hedged_claim": "the claim is hedged",
        "supported_recommendation": "the recommendation is backed by evidence the document gives",
        "factual_policy_mention": "it factually describes what a policy says",
        "skipped_section": "it sits in a section the check skips",
        "descriptive_usage": "the word describes something rather than pushing a position",
    },
)
