"""The Concision & Precision annotation set; guidance paraphrases its skill for a person."""

from lib.services.annotations.set_spec import AnnotationSetSpec, should_flag_question

CONCISION_PRECISION = AnnotationSetSpec(
    slug="concision_precision",
    title="Concision & Precision",
    workflow_type="concision_precision",
    summary="Is the highlighted sentence wordier or vaguer than it needs to be?",
    guidance="""\
The check flags sentences that cost the reader effort without adding meaning:

- **Wordy constructions** that a shorter phrasing says just as well (*in order to*, *due to the fact that*, *each and every*, filler like *very*, *basically* or *indeed*). They count anywhere in a sentence, not only at its start, and every one in a paragraph counts, not just the first:
  - wordy connectors: *in the case of* (for), *with regard to* (on), *in addition to* (besides), *and also* (and);
  - a connector set off by commas mid-clause: *would, therefore, benefit* (would therefore benefit);
  - *as* meaning *because* at the head of a clause, where *because* is clearer;
  - near-synonym pairs where the second word adds nothing (*goals and objectives*);
  - padding words (*benefit from carrying out regular audits* for *benefit from regular audits*).
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
    questions=[should_flag_question()],
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
