"""The Headers & Skimmability annotation set; guidance paraphrases its skill for a person."""

from lib.services.annotations.set_spec import AnnotationSetSpec, should_flag_question

HEADERS_SKIMMABILITY = AnnotationSetSpec(
    slug="headers_skimmability",
    title="Headers & Skimmability",
    workflow_type="headers_skimmability",
    summary="Could a reader skimming the highlighted header or lead sentence get the point?",
    guidance="""\
A reader skimming only the headers, the bold lead sentences and the opening should come away with the report's main points. The highlighted passage may be a header, a bold opener, the opening section or a key finding.

The check flags:

- **Vague header:** a findings or discussion section headed by a generic label that would fit any report (*Findings*, *Results*, *Discussion*, *Key Themes*).
- **Header lacks takeaway:** the header names the subject but not what the section found (*Analysis of Court Staffing Levels* over a section showing staffing fell short everywhere).
- **Header does not match content:** the header promises something the section does not deliver, or names a different subject.
- **Bottom line not up front:** the opening describes purpose, background or method but never states the main finding.
- **Lead sentence lacks takeaway:** a bold opener that only names a topic (**Retention.**) when the paragraph under it makes a claim the opener could state.
- **Key findings box** with more than about six items, or items that are not brief and direct.

It leaves these alone:

- Sections readers look for by name (*Summary*, *Introduction*, *Conclusion*, *Recommendations*).
- Methods, background, limitations and other procedural headers (*How We Selected the Sites*), and front and back matter.
- Protected headers (*Key Findings*, anything starting with *Option*) and headers naming the alternatives being compared (*Scenario B: Signing Bonuses*).
- The document's title, headers that already state the point, signposting sentences, run-in labels on procedural content, and bold used for emphasis inside a sentence.
""",
    questions=[should_flag_question()],
    decoy_reasons={
        "procedural_header": "it heads a methods, background or other procedural section, so a label is fine",
        "signposting": "it is signposting that orients the reader",
        "document_title": "it is the document's title, not a section header",
        "named_section": "readers look for this section by name",
        "argued_lead": "the bold opener already makes a point",
        "procedural_lead": "it is a run-in label on procedural content",
        "protected_header": "it is a protected header",
        "alternative_header": "it names one of the alternatives the report compares",
        "bold_emphasis": "the bold is emphasis inside a sentence, not a lead sentence",
    },
)
