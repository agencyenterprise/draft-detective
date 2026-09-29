"""The Writing Consistency annotation set; guidance paraphrases its skill for a person."""

from lib.services.annotations.set_spec import AnnotationSetSpec, should_flag_question

WRITING_CONSISTENCY = AnnotationSetSpec(
    slug="writing_consistency",
    title="Writing Consistency",
    workflow_type="writing_consistency",
    summary="Does the highlighted passage disagree with how the rest of the document says the same thing?",
    guidance="""\
An inconsistency needs two places, so the highlighted passage is one side of it: look through the document for the other before judging.

The check flags:

- **Inconsistent term:** the same thing called by different names (*participants* and *respondents* for the same people, *Grade 3* and *third grade*).
- **Inconsistent spelling or capitalization:** *health care* and *healthcare*, *organisation* and *organization*, *the Department* and *the department* for the same body.
- **Inconsistent hyphenation:** the same compound hyphenated in one place and open in another, in the same position (*next-generation models*, *next generation models*).
- **Inconsistent number style:** *percent* and *%*, *nine* and *9* for counts in the same range.
- **Inconsistent tense:** findings in the past tense in one section and the present in another.
- **Inconsistent tone:** a shift in register between passages of the same kind, such as first person in one chapter and *the authors* in another.
- **House style:** *decision-making* or *decision making* anywhere; the house form is *decisionmaking*.

It leaves these alone:

- Different terms for different things, and a term spelled out once and then shortened (*the Community Health Program*, then *the program*).
- Quoted wording, titles, and names spelled the way their owners spell them.
- A compound hyphenated before a noun and open after a verb (*a long-term plan*; *the plan is long term*), and singular against plural.
- Present tense for general truths, for interpreting the findings, or for what the document itself does (*this chapter describes*).
- Tables, which follow their own conventions, and anything that appears only once.
""",
    questions=[should_flag_question()],
    decoy_reasons={
        "glossed_short_form": "the term is spelled out once and then shortened",
        "different_things": "the two terms name different things",
        "quoted": "it is quoted wording or a title that keeps its own spelling",
        "proper_name": "it is a name spelled the way its owner spells it",
        "predicate_position": "a compound is hyphenated before a noun and open after a verb, which is correct",
        "table": "tables follow their own conventions",
        "general_truth": "it states something generally true, so the present tense is right",
        "signposting_tense": "it describes what the document itself does, so the present tense is right",
        "consistent_style": "its style matches the rest of the document",
        "plural": "singular against plural is not a variant",
        "interpretation_tense": "it interprets the findings, so the present tense is right",
    },
)
