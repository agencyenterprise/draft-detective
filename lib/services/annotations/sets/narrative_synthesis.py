"""The Narrative & Synthesis annotation set; guidance paraphrases its skill for a person."""

from lib.services.annotations.set_spec import AnnotationSetSpec, should_flag_question

NARRATIVE_SYNTHESIS = AnnotationSetSpec(
    slug="narrative_synthesis",
    title="Narrative & Synthesis",
    workflow_type="narrative_synthesis",
    summary="Does the highlighted passage tell the reader what the evidence means, in an order that builds?",
    guidance="""\
The report should read as one connected argument that interprets its evidence and answers three questions: *Why should I care? What's different about this? What happens next?* Read the whole document before judging the passage.

The check flags:

- **Data without synthesis:** a run of figures, survey results, quotations or facts with no sentence saying what they show or why they matter. One number in a sentence that makes a point is fine; three or more strung together with no takeaway is not.
- **Illogical order:** material the reader meets before they need it, such as findings before the method that produced them, or recommendations before the findings they rest on.
- **Missing framing:** nothing in the document answers one of the three questions.
- **Restated point:** a later section repeats, at length, a point already made elsewhere instead of building on it.

It leaves these alone:

- Data whose own sentences, or the next sentence, say what they show; a single comparison that makes its own point; findings stated in words.
- Tables and figures, pointers to them, and numbers that describe how the study was done.
- Appendices, and summaries, key findings and chapter recaps, which restate points on purpose.
- Brief references back (*As Chapter 2 showed...*) and signposting.
- A framing question answered anywhere in the document, and a conventional report order.
- Headers and whether the opening states the bottom line, which a separate check covers.
""",
    questions=[should_flag_question()],
    decoy_reasons={
        "methods_description": "the numbers describe how the study was done",
        "interpreted_data": "the passage says what its data show",
        "signposting": "it is signposting that orients the reader",
        "interpretation_follows": "the next sentence says what the data mean",
        "table_or_figure": "it presents or points to a table or figure",
        "single_statistic": "it is one figure inside a sentence that makes a point",
        "appendix_data": "it sits in an appendix, where raw data belong",
        "summary_restatement": "it sits in a summary, which restates points on purpose",
        "chapter_summary": "it is a chapter summary, which recaps on purpose",
        "framing_elsewhere": "it answers a framing question, which may sit anywhere in the document",
        "cross_reference": "it briefly refers back to an earlier point",
        "single_comparison": "it sets figures side by side in one comparison, which makes its own point",
        "header_mismatch": "whether a header matches its section is a separate check",
        "plain_header": "headers are a separate check",
    },
)
