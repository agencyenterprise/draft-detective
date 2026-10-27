# About This Tool

## What is This Tool?

This is an AI-powered document review tool that runs a suite of targeted checks across language, citations, technical compliance, and substantive content — surfacing issues directly in your document. The tool is under active development; new analysis types and features are added on a rolling basis.

---

## Data Protection

- This tool is hosted within a managed cloud environment.
- We use approved LLMs under the hood.
- For certain analyses (reference checks, literature reviews, etc.), you must opt-in to web search to enable the analysis. If you do this, portions of your document may be included in the web search (typically, reference check only uses the references).

---

## Inputs & Outputs

**Input:** Upload your draft document (.docx recommended; PDF also supported). You can upload just a section of your document — for example, only the references section — if you prefer not to share the full draft.

**Output:** View findings in-browser using the Document Explorer, or export to Word as tracked comments. Projects can be shared with colleagues via a read-only link.

---

## Tips

- **Experimental analysis types are hidden by default.** To enable them, click your profile picture in the top right corner and toggle on "Experimental Features". Once enabled, experimental analysis types will appear as an expandable section in the analysis selection step.
- **Most checks only need your document.** *Claim Reference Validation* requires uploading or fetching the full text of your references. The app will prompt you when this is needed.
- **You can upload just a section** of your document if you prefer — for example, references only for citation checks.

---

## Analysis Types

Each check is listed below, organized by category and shown in the order it appears in the app. Evaluation coverage is in active development — see the [evals folder on GitHub](https://github.com/agencyenterprise/draft-detective/tree/main/evals_inspectai) for details.

### Citation Check

| Analysis Type | Description | Eval |
|:---|:---|:---:|
| **Reference Error Checker** | Uses web search to check whether each reference is findable online and whether the author, title, year, and publisher match public sources — useful for catching reference typos or hallucinated citations. `#web_search` | [eval](https://github.com/agencyenterprise/draft-detective/tree/main/evals_inspectai/e2e/reference_validation_v2) |

### Substantive Review

| Analysis Type | Description | Eval |
|:---|:---|:---:|
| **Claim Reference Validation** | Checks every citation against its referenced source using retrieval-augmented generation (RAG), returning a verdict for each claim: supported, partially supported, unsupported, or unverifiable. Requires the full text of your references — the app fetches them or you upload them. `#full_text_refs` | [eval](https://github.com/agencyenterprise/draft-detective/tree/main/evals_inspectai/e2e/claim_reference_validation_v2) |
| **Internal Inference Validation** | Analyzes the full document for invalid inferences, identifying logical fallacies, unsupported conclusions, and faulty reasoning. Each finding includes the key sentence, an analysis of the argument, and a suggested correction. | [eval](https://github.com/agencyenterprise/draft-detective/tree/main/evals_inspectai/e2e/inference_validation_v2) |
| **Methodological Alignment** | Uses web search to characterize standard methods in the field, then compares the document's methodology against them — highlighting similarities, gaps, and risks. `#web_search` | |
| **Reproducibility Check** | Extracts the document's main results and classifies each by how reproducible it is, based on whether the underlying data is present and the methodology is described. `#experimental` | |
| **Reviewer 2** | Simulates a full peer review of the kind a senior researcher would write — producing a structured review with strengths, weaknesses, actionable next steps, and a devil's-advocate rebuttal. Unlike the other checks, which each target a specific issue, Reviewer 2 gives an integrated evaluation of the document as a whole. `#experimental` | |
| **Recommendation Check** | Checks whether each recommendation is supported by the document's own findings, flagging recommendations whose backing is weak, indirect, missing, or contradictory. `#experimental` | [eval](https://github.com/agencyenterprise/draft-detective/tree/main/evals_inspectai/e2e/recommendation_check) |

### Editorial and Style Review

| Analysis Type | Description | Eval |
|:---|:---|:---:|
| **Abbreviation Scan** | Scans the document for abbreviations and acronyms, verifies each is defined inline at its first occurrence, and checks that all abbreviations appear in an Abbreviations section. | [eval](https://github.com/agencyenterprise/draft-detective/tree/main/evals_inspectai/e2e/abbreviation_checker) |
| **Figures & Tables Check** | Verifies that every figure and table has a title, is consistently numbered, is referenced in the body text, and that every body-text reference resolves to an actual figure or table in the document. | [eval](https://github.com/agencyenterprise/draft-detective/tree/main/evals_inspectai/e2e/figures_tables_check) |
| **Structural Checks (GER)** | Checks that the report has every required section (About This, About the Authors, Acknowledgements, Methods, Results, Conclusion, References, and an Appendix when the text refers to one), that its preface states its context, objectives, audience, place in the literature, contribution and scope, and that each author biography gives a position and affiliation, research focus and highest degree in three sentences. Tailored to RAND GER publications. | [eval](https://github.com/agencyenterprise/draft-detective/tree/main/evals_inspectai/e2e/structural_checks_ger) |

### Language

| Analysis Type | Description | Eval |
|:---|:---|:---:|
| **Advocacy & Tone** | Flags trigger words, advocacy language, and subjective tone — language that departs from a neutral, objective voice. | [eval](https://github.com/agencyenterprise/draft-detective/tree/main/evals_inspectai/e2e/advocacy_tone_v2) |

---

## Source Code

The source code is available on [GitHub](https://github.com/agencyenterprise/draft-detective).
