---
name: document-contents
description: Use this skill to check that a document contains all required top-level sections — About This, Acknowledgements, Methods, Results, Conclusion, References, and a conditional Appendix. Invoke when asked to verify a document's structure or that its required sections/content are present.
---

# Document Contents

You are a specialist document reviewer. Check that the document contains each required section below and report any that are missing. Read or search the document's content as needed to evaluate each section.

## Required Sections

Check whether the document contains each of the required sections listed below. For every section that is **missing**, report one issue. For sections that are present, do **not** create an issue.

Evaluate each section by looking for a heading (at any level) or a clearly labelled block of text that serves the purpose of that section. Treat variations in capitalisation and minor wording differences as a match (e.g. "Reference List", "Bibliography", or "Works Cited" all satisfy the **References** requirement).

### 1 — About This

A preface, foreword, or introductory section that explains the purpose, context, and scope of the publication. Common headings: "About This Report", "About This Publication", "Preface", "Foreword", "Introduction".

**If missing → issue title:** "Missing Section: About This"

### 2 — Acknowledgements

A section that credits individuals, organisations, or funding bodies that contributed to the work. Common headings: "Acknowledgements", "Acknowledgments", "Thanks".

**If missing → issue title:** "Missing Section: Acknowledgements"

### 3 — Methods

A section describing the research methodology, data sources, or analytical approach used in the study. Common headings: "Methods", "Methodology", "Research Design", "Data and Methods", "Approach".

**If missing → issue title:** "Missing Section: Methods"

### 4 — Results

A section presenting the key findings or outcomes of the research. Common headings: "Results", "Findings", "Key Findings", "Outcomes".

**If missing → issue title:** "Missing Section: Results"

### 5 — Conclusion

A section summarising the main conclusions, implications, or recommendations. Common headings: "Conclusion", "Conclusions", "Discussion", "Summary", "Recommendations".

**If missing → issue title:** "Missing Section: Conclusion"

### 6 — References

A section listing the bibliographic references cited in the document. Common headings: "References", "Bibliography", "Works Cited", "Reference List", "Sources".

**If missing → issue title:** "Missing Section: References"

### 7 — Appendix (conditional)

Only check for this section if the body text **explicitly mentions** an appendix (e.g. "see Appendix A", "as shown in the appendix"). If such a reference exists but no appendix section is present in the document, add an issue. If there is no reference to an appendix in the body text, skip this check entirely. Common headings: "Appendix", "Appendix A", "Supplementary Material".

**If referenced but missing → issue title:** "Missing Section: Appendix"

## Reporting

For each missing section, report one issue following the conventions defined in the `issues` skill. Do not create issues for sections that are present.
