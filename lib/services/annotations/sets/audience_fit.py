"""The Audience Fit annotation set; guidance paraphrases its skill for a person."""

from lib.services.annotations.set_spec import AnnotationSetSpec, should_flag_question

AUDIENCE_FIT = AnnotationSetSpec(
    slug="audience_fit",
    title="Audience Fit",
    workflow_type="audience_fit",
    summary="Does the report name a specific audience, and does the highlighted passage suit it?",
    guidance="""\
First decide who the report is for, from its front matter or introduction, or failing that from who could act on its findings. Then judge the passage against that reader.

The check flags:

- **Target audience missing:** the front matter and introduction never say who the report is for or who should use its findings.
- **Target audience too vague:** the audience is only a generic label (*policymakers*, *stakeholders*, *decisionmakers*, *the public*).
- **Target audience conflict:** the front matter and the introduction describe substantively different audiences.
- **Technical language,** when the audience is not technical: statistical or methodological terms (*regression*, *fixed effects*, *p-value*, *causal inference*), equations, or a field's specialist terms the reader would stop on. Also a run of main-body paragraphs given over to technical detail that belongs in an appendix.

It leaves these alone:

- An audience with any narrowing qualifier (*state education policymakers*, *hospital administrators*), and two descriptions that differ in wording but agree.
- Technical language when the audience is researchers or analysts, or the report is about a new method.
- Anything in an appendix, and pointers to it (*Appendix B describes the model*).
- The audience's own working vocabulary (*Title I*, *WIOA*, *Medicaid managed care*).
- Plain descriptions of method and numbers (*we surveyed 212 teachers*, percentages, averages).
- A term explained where it is used, quoted wording, headings and reference lists.
""",
    questions=[should_flag_question()],
    decoy_reasons={
        "plain_method": "it describes the method in plain words",
        "plain_numbers": "the numbers are plain counts, percentages or averages",
        "specific_audience": "the audience it names is specific enough",
        "audience_vocabulary": "the term is part of the named audience's own vocabulary",
        "reworded_audience": "the two audience descriptions differ in wording but agree",
        "technical_audience": "the report is written for a technical audience, so technical language is fine",
        "explained_term": "the term is explained where it is used",
        "appendix_pointer": "it points the reader to the technical material in an appendix",
        "quoted": "it is quoted wording",
        "appendix": "it sits in an appendix, where technical content belongs",
    },
)
