"""The Active Voice & Clear Actors annotation set; guidance paraphrases its skill for a person."""

from lib.services.annotations.set_spec import AnnotationSetSpec, should_flag_question

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
    questions=[should_flag_question()],
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
