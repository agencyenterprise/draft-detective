"""The Sentence Structure annotation set; guidance paraphrases its skill for a person."""

from lib.services.annotations.set_spec import AnnotationSetSpec, should_flag_question

SENTENCE_STRUCTURE = AnnotationSetSpec(
    slug="sentence_structure",
    title="Sentence Structure",
    workflow_type="sentence_structure",
    summary="Is the highlighted sentence built so that it fails to parse or buries its point?",
    guidance="""\
The check flags sentences whose structure trips the reader:

- **Incomplete sentences:** a body sentence missing a word it needs, such as its verb (*The research questions summarized in Table 2.*), a dropped preposition, or a *because* clause with no main clause.
- **Broken shared constructions:** two verbs or prepositions sharing one object that fits only one of them (*raised the profile of and normalized apprenticeships*, *as good or better than*, *interested and committed to*).
- **Faulty parallelism:** a pair or series built in different forms (*both X, as well as Y*; *to recruit, training, and to place*; *not only X but Y*).
- **Indirect summary sentences:** only two lead-ins: the authors' own recommendations, conclusions or lessons said to *emerge* or *arise* (*Several recommendations emerged from the analysis*), and *It is in Table 4 that the costs are presented*.

It leaves these alone:

- Shared constructions where each half works on its own (*we collected and analyzed the data*, *access to and use of services*).
- Correct pairs and series (*both X and Y*), and *as well as* on its own.
- Bullet points, captions and table cells written as phrases.
- Themes or patterns that emerge from data, and lead-ins that already lead with the table or content (*Table 2 summarizes...*).
- Placeholder or wordy lead-ins (*It is possible to estimate...*, *These numbers are reflective of...*), which Concision & Precision covers.
- Long sentences that parse, quoted wording, and sentences whose only problem is passive voice, wordiness or tense, which other checks cover.
""",
    questions=[should_flag_question()],
    decoy_reasons={
        "grammatical_shared": "each half of the shared construction works on its own",
        "correct_correlative": "the pair is correctly built",
        "parallel_series": "the series items share one form",
        "as_well_as": "*as well as* on its own needs no *both*",
        "list_fragment": "it is a list item or caption, not a body sentence",
        "emergent_finding": "themes or patterns can emerge from data",
        "direct_leadin": "it already leads with what it introduces",
        "long_parses": "it is long, but it parses",
        "quoted": "it is quoted wording",
        "other_check": "its only problem belongs to another Writing Style check",
        "hedged_summary": "it keeps its hedge, and the sentence before it is a separate sentence",
    },
)
