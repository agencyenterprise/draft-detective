from lib.services.app_configs import DefaultConfig

ABOUT_PAGE_CONTENT_KEY = "about_page.content"

ABOUT_PAGE_DEFAULT_CONTENT = """\
# About This Tool

## What is This Tool?

This is an AI-powered document review tool that runs a suite of targeted checks across language, \
citations, technical compliance, and substantive content — surfacing issues directly in your document. \
The tool is under active development; new analysis types and features are added on a rolling basis.

---

## Data Protection

- This tool is hosted within a managed cloud environment.
- We use approved LLMs under the hood.
- For certain analyses (reference checks, literature reviews, etc.), you must opt-in to web search \
to enable the analysis. If you do this, portions of your document may be included in the web search \
(typically, reference check only uses the references).

---

## Inputs & Outputs

**Input:** Upload your draft document (.docx recommended; PDF also supported). You can upload just \
a section of your document — for example, only the references section — if you prefer not to share \
the full draft.

**Output:** View findings in-browser using the Document Explorer, or export to Word as tracked \
comments. Projects can be shared with colleagues via a read-only link.

---

## Tips

- **Experimental analysis types are hidden by default.** To enable them, click your profile picture \
in the top right corner and toggle on "Experimental Features". Once enabled, experimental analysis \
types will appear as an expandable section in the analysis selection step.
- **Most checks only need your document.** A few require uploading or fetching the full text of your \
references: *Claim Reference Validation* and *Citation Suggester*. The app will prompt you when these \
are needed.
- **You can upload just a section** of your document if you prefer — for example, references only for \
citation checks.

---

## Analysis Types

Each check is listed below, organized by category. Evaluation coverage is in active development — \
see the [evals folder on GitHub](https://github.com/agencyenterprise/ai-reviewer/tree/main/evals_inspectai) \
for details.

### Language

| Analysis Type | Description | Eval |
|:---|:---|:---:|
| **Advocacy & Tone** | Checks for trigger words, advocacy language, and subjective tone using a two-layer approach — first fast pattern-matching, then LLM verification. Flags language that departs from a neutral, objective tone. | |

### Technical Compliance

| Analysis Type | Description | Eval |
|:---|:---|:---:|
| **Abbreviation Scan** | Scans the document for abbreviations and acronyms, verifies each is defined inline at its first occurrence, and checks that all abbreviations appear in an Abbreviations section. | [eval](https://github.com/agencyenterprise/ai-reviewer/tree/main/evals_inspectai/e2e/abbreviation_checker) |
| **Document Structure** | Checks that key sections are present: Acknowledgements, Methods, Results, Conclusion, References, and Appendix (if referenced in text). `#experimental` | [eval](https://github.com/agencyenterprise/ai-reviewer/tree/main/evals_inspectai/e2e/document_structure) |
| **Figures & Tables Check** | Verifies that every figure and table has a title, is consistently numbered, is referenced in the body text, and that every body-text reference resolves to an actual figure or table in the document. `#experimental` | [eval](https://github.com/agencyenterprise/ai-reviewer/tree/main/evals_inspectai/e2e/figures_tables_check) |

### Citation Check

| Analysis Type | Description | Eval |
|:---|:---|:---:|
| **Reference Error Checker** | Uses web search to check whether each reference is findable online and whether the author, title, year, and publisher match public sources — useful for catching reference typos or hallucinated citations. `#web_search` | [eval](https://github.com/agencyenterprise/ai-reviewer/tree/main/evals_inspectai/e2e/reference_validation) |

### Substantive Review

| Analysis Type | Description | Eval |
|:---|:---|:---:|
| **Claim Reference Validation** | Validates claims against supporting documents using retrieval-augmented generation (RAG). Retrieves relevant passages from uploaded reference PDFs and returns a verdict for each claim: supported, partially supported, unsupported, or unverifiable. `#full_text_refs` | [component evals](https://github.com/agencyenterprise/ai-reviewer/tree/main/tests/evals/llm) |
| **Inference Validation** | Analyzes the full document for invalid inferences, identifying logical fallacies, unsupported conclusions, and faulty reasoning. Each finding includes the key sentence, an analysis of the argument, and a suggested correction. | |
| **Methodological Alignment** | Compares the methodology used in the document against typical methods in the field, using web search to gather field context and highlight gaps or risks. `#web_search` | |
| **Results Extraction** | Extracts the document's main results and assesses their reproducibility — returning a structured list of findings (figures, tables, equations, key text) each with a reproducibility classification and rationale. | |
| **Reviewer 2** | Simulates a full peer review of the kind a senior researcher would write — producing a structured review with strengths, weaknesses, actionable next steps, and a devil's-advocate rebuttal. Unlike the other checks, which each target a specific issue, Reviewer 2 gives an integrated evaluation of the document as a whole. `#experimental` | |

### Research & Writing Assistant

| Analysis Type | Description | Eval |
|:---|:---|:---:|
| **Literature Review** | Searches the web for relevant academic sources related to your document's claims that you may not have cited, noting for each whether it supports or conflicts with your work. `#experimental` `#web_search` | |
| **Citation Suggester** | Identifies claims that would benefit from additional citations and recommends specific references from your uploaded supporting documents. Can be paired with Literature Review to suggest newly discovered sources. `#experimental` `#web_search` `#full_text_refs` | [component evals](https://github.com/agencyenterprise/ai-reviewer/tree/main/tests/evals/llm) |
| **Live Reports** | Analyzes claims against sources published after the document's date, identifying findings that may need updating in light of newer evidence and generating a consolidated addendum. `#experimental` `#web_search` | |

---

## Source Code

The source code is available on [GitHub](https://github.com/agencyenterprise/ai-reviewer).
"""

ABOUT_PAGE_DEFAULTS = [
    DefaultConfig(
        key=ABOUT_PAGE_CONTENT_KEY,
        default_value=ABOUT_PAGE_DEFAULT_CONTENT,
        description=(
            "Markdown content displayed on the About page. "
            "Supports full GitHub-flavored Markdown including tables and links."
        ),
    ),
]
