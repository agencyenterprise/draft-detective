"""The annotation sets users can work on, and where their items come from.

Each set is built from an issue-inventory eval dataset: every expected issue
and every decoy with an anchor becomes one "should this passage be flagged?"
item. Guidance paraphrases the workflow's skill for a person, not a model.
"""

from pathlib import Path

from pydantic import BaseModel, Field

from lib.services.annotations.models import AnnotationOption, AnnotationQuestion

EVALS_ROOT = Path(__file__).resolve().parents[3] / "evals_inspectai" / "e2e"

SHOULD_FLAG = "should_flag"


class AnnotationSetSpec(BaseModel):
    """A set's definition in code; the sync writes it to the database."""

    slug: str
    title: str
    workflow_type: str
    summary: str
    guidance: str
    questions: list[AnnotationQuestion]
    decoy_reasons: dict[str, str] = Field(
        default_factory=dict,
        description="Plain-language reading of each decoy reason, for the admin results view",
    )

    @property
    def dataset_path(self) -> Path:
        return EVALS_ROOT / self.slug / "dataset.yaml"


# One wording for every set: the rules that make it specific sit right below it.
SHOULD_FLAG_PROMPT = (
    "Should Draft Detective flag the highlighted passage according to the rules below?"
)


def _should_flag_question() -> AnnotationQuestion:
    return AnnotationQuestion(
        key=SHOULD_FLAG,
        prompt=SHOULD_FLAG_PROMPT,
        options=[
            AnnotationOption(value="yes", label="Yes, flag it", shortcut="1"),
            AnnotationOption(value="no", label="No, leave it", shortcut="2"),
            AnnotationOption(value="unsure", label="Not sure", shortcut="3"),
        ],
        abstain_value="unsure",
    )


ACTIVE_VOICE = AnnotationSetSpec(
    slug="active_voice",
    title="Active Voice & Clear Actors",
    workflow_type="active_voice",
    summary="Is the highlighted sentence passive when it should be active, or does it hide who is responsible?",
    guidance="""\
The check flags two kinds of sentence:

- **Passive voice that hides or buries a nameable actor.** *Data were collected from three sites*, when the text makes clear who collected them, or when leaving the actor out hides who decided, funded, approved or will carry out something.
- **Ambiguous actors.** An inanimate subject standing in for people (*the evaluation will assess...*) when several organizations share the work, so the reader cannot tell who does it.

It leaves these alone:

- Passives whose only actor is "whoever does this" (*barriers that can be addressed*).
- States rather than actions (*is limited to*, *is based on*, *were eligible*) and idioms (*is expected to*, *is meant to*).
- Participles describing a noun (*an institution funded by 24 member states*).
- First person (*we surveyed*), source qualifiers (*staff reported that*), quoted or cited wording, headings and reference lists.
- A sentence whose point is naming the actor, or where the active version would read worse.
""",
    questions=[_should_flag_question()],
    decoy_reasons={
        "active": "the sentence is already active",
        "qualifier": "it attributes a finding to its source",
        "participial": "the participle describes a noun rather than serving as the verb",
        "stative": "it describes a state, not an action someone performed",
        "quoted": "it is quoted wording",
        "excluded": "it sits in material the check skips, such as a heading or reference list",
        "generic": 'the only possible actor is "whoever does this"',
        "actor_is_the_point": "the sentence is about naming the actor",
        "source_definition": "it is a cited source's own definition",
        "idiom": "the participle is part of an idiom expressing intent or likelihood",
    },
)

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
    questions=[_should_flag_question()],
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

CONCISION_PRECISION = AnnotationSetSpec(
    slug="concision_precision",
    title="Concision & Precision",
    workflow_type="concision_precision",
    summary="Is the highlighted sentence wordier or vaguer than it needs to be?",
    guidance="""\
The check flags sentences that cost the reader effort without adding meaning:

- **Wordy constructions** that a shorter phrasing says just as well (*in order to*, *due to the fact that*, *each and every*, filler like *very* or *basically*).
- **Run-on sentences:** two complete thoughts joined by a comma alone, or a chain of thoughts the reader has to hold past the end.
- **Throat-clearing and empty framing:** sentences that delay or promise a point without making one (*This is a complex issue.*).
- **Vague references:** a bare *this* or *these factors* when the earlier text offers more than one thing it could mean.
- **Obvious statements** presented as a finding (*Funding is essential to running a program.*).

It leaves these alone:

- Signposting (*In this section, we describe...*) and topic sentences that announce what the paragraph then gives.
- Source qualifiers (*staff reported that*) and hedges that carry meaning (*may*, *in most cases*).
- Compound sentences joined by *, and* or *, but*, and two clear sentences side by side.
- Long sentences whose every clause carries information, technical terms the audience knows, and first person.
- References that name their referent (*the two groups*), quoted wording, headings and reference lists.
""",
    questions=[_should_flag_question()],
    decoy_reasons={
        "signposting": "it orients the reader to what comes next",
        "qualifier": "it attributes a finding to its source",
        "hedge": "the hedge carries meaning",
        "compound": "it is an ordinary compound sentence",
        "first_person": "first person is fine",
        "topic_sentence": "it is a topic sentence the paragraph then fills in",
        "clear_referent": "what it refers to is clear from the previous sentence",
        "technical_term": "it uses a technical term the audience knows",
        "long_precise": "it is long, but every clause carries information",
        "quoted": "it is quoted wording",
        "two_sentences": "they are two clear sentences",
        "aims_sentence": "it states the framework's aims, which is content",
    },
)

ANNOTATION_SETS: list[AnnotationSetSpec] = [
    ACTIVE_VOICE,
    ADVOCACY_TONE,
    CONCISION_PRECISION,
]
