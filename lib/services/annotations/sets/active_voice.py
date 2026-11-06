"""The Active Voice & Clear Actors annotation set; guidance paraphrases its skill for a person."""

from lib.services.annotations.set_spec import AnnotationSetSpec, should_flag_question

ACTIVE_VOICE = AnnotationSetSpec(
    slug="active_voice",
    title="Active Voice & Clear Actors",
    workflow_type="active_voice",
    summary="Is the highlighted sentence passive when it should be active, or does it hide who is responsible?",
    guidance="""\
The check flags four kinds of sentence:

- **Passive voice that hides or buries a nameable actor.** *Data were collected from three sites*, when the text makes clear who collected them, or when leaving the actor out hides who decided, funded, approved or will carry out something. A passive counts wherever it sits, including inside a *which* or *that* clause in the middle of a long sentence (*a backlog, which was later made worse by the move to a new system*).
- **Passives that state what something is for.** *The pilot was designed to reduce wait times* reads better as *The pilot aimed to reduce wait times*, so it is flagged even when the text never says who designed it. This does not cover a choice someone made for their own reasons (*the site was selected to reduce costs*), which still hides who chose.
- **Ambiguous actors.** An inanimate subject standing in for people (*the evaluation will assess...*) when several organizations share the work, so the reader cannot tell who does it.
- **Indirect summary sentences.** The authors' own recommendations, conclusions or lessons said to *emerge*, *arise* or *surface* by themselves (*Several recommendations emerged from the analysis*). A signposting passive wrapped in a cleft (*It is in Table 4 that the costs are presented*) is flagged as passive voice and rewritten as *Table 4 presents the costs*.

It leaves these alone:

- Passives whose only actor is "whoever does this" (*barriers that can be addressed*).
- States rather than actions (*is limited to*, *is based on*, *were eligible*) and idioms (*is expected to*, *is meant to*).
- Participles describing a noun (*an institution funded by 24 member states*).
- First person (*we surveyed*), source qualifiers (*staff reported that*), quoted or cited wording, headings and reference lists.
- A sentence whose point is naming the actor, or where the active version would read worse.
- Themes or patterns that emerge from data (*Three themes emerged from the interviews*), and placeholder or wordy lead-ins (*It is possible to estimate...*), which Concision & Precision covers.
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
        "emergent_finding": "themes or patterns can emerge from data",
        "other_check": "its only problem belongs to another Writing Style check",
    },
)
