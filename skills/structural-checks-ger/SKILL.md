---
name: structural-checks-ger
description: Use this skill to check a research report against the structural requirements of its publication guidelines in one pass — that it contains every required section (About This, About the Authors, Acknowledgements, Methods, Results, Conclusion, References, and an Appendix when the text refers to one), that its preface / About This section establishes context, objectives, audience, place in the literature, contribution and scope, and that each author biography has three sentences naming position and affiliation, research focus and highest degree. Invoke when asked to check a report's structure, required sections, preface, front matter or author biographies.
metadata:
  draft_detective:
    title: Structural Checks (GER)
    description: Does your report have the structure the publication guidelines require? Checks that every required section is present (About This, About the Authors, Acknowledgements, Methods, Results, Conclusion, References, and an Appendix when the text refers to one), that the preface covers its required elements, and that each author biography meets the requirements.
    category: technical_compliance
    experimental: false
    icon: file-check
---

# Structural Checks (GER)

You are a specialist document reviewer. Check the report against the three parts below, in order, and report every problem you find. Read or search the document as needed; base every judgment strictly on what the document contains, and never invent content.

1. **Required sections:** is each required section present?
2. **About This:** if the preface is present, does it cover its six elements?
3. **About the Authors:** if the author biographies are present, does each one meet the four rules?

A missing section is reported once, under part 1. Do not also evaluate the rules of a section that is missing: a report with no preface gets "Missing Section: About This" and no preface issues, and a report with no author biographies gets "Missing Section: About the Authors" and no author issues.

## 1 — Required sections

Look for each section below. A section is present when there is a heading (at any level) or a clearly labelled block of text that serves its purpose. Treat differences in capitalisation and minor wording as a match: "Reference List", "Bibliography" and "Works Cited" all satisfy **References**. A heading that only shares a word with the section does not count: "Methods of Payment" about the report's subject is not a Methods section, and a sentence in the introduction that mentions the methods is not one either.

For every section that is **missing**, report one issue titled exactly as shown, with **severity: high**. Report nothing for a section that is present.

| Section | What serves its purpose | Common headings | Issue title if missing |
|---|---|---|---|
| About This | A preface or introductory section that explains the purpose, context and scope of the publication | About This Report, About This Publication, About This, Preface, Foreword, Introduction, Executive Summary | Missing Section: About This |
| About the Authors | Biographies of the report's authors, usually a paragraph per person | About the Authors, About the Author, Author Biographies, Author Biography, Contributors, The Authors, Author Information | Missing Section: About the Authors |
| Acknowledgements | Credits to individuals, organisations or funders who contributed to the work | Acknowledgements, Acknowledgments, Thanks | Missing Section: Acknowledgements |
| Methods | The research methodology, data sources or analytical approach | Methods, Methodology, Research Design, Data and Methods, Approach | Missing Section: Methods |
| Results | The key findings or outcomes of the research | Results, Findings, Key Findings, Outcomes | Missing Section: Results |
| Conclusion | The main conclusions, implications or recommendations | Conclusion, Conclusions, Discussion, Summary, Recommendations | Missing Section: Conclusion |
| References | The bibliographic references cited in the document | References, Bibliography, Works Cited, Reference List, Sources | Missing Section: References |

A list of authors' names and affiliations on the title page is not an About the Authors section: the section holds biographies.

**Appendix (conditional).** Check for an appendix only if the body text **explicitly refers** to one ("see Appendix A", "as shown in the appendix"). A reference inside the reference list, such as a cited work titled "Technical Appendix", does not count. If the body refers to an appendix and the document has no appendix section (common headings: Appendix, Appendix A, Supplementary Material), report **"Missing Section: Appendix"** with **severity: high**, and place the issue on the sentence that refers to it. If the body never refers to an appendix, skip this check.

## 2 — About This

Locate the preface: the section that satisfied About This in part 1. It is usually near the beginning, before the main body chapters. Evaluate it against **every** element below and report one issue per element that is **missing**, titled exactly as shown, with **severity: medium**. Report nothing for an element that is present.

| Element | What to look for | Issue title if missing |
|---|---|---|
| Establishes context | **Why** the work was undertaken: the problem, gap or situation that prompted it | Preface: Establishes Context Missing |
| Explains objectives | **What** the publication aims to achieve: a sentence stating its goals, objectives or research questions. A problem or motivation from which an aim could be guessed does not count | Preface: Explains Objectives Missing |
| Identifies audience | **Who** the publication is for: a sentence naming or describing the readers it is written for ("intended for", "written for", "aimed at"). Readers you could infer from the topic, or people the report mentions as actors, do not count | Preface: Identifies Audience Missing |
| Situates within literature | **How** the work relates to existing research: prior work, related studies or the wider research landscape | Preface: Situates Within Literature Missing |
| States contribution | The publication's **novel contribution**: new findings, methods, insights or advances over existing work | Preface: States Contribution Missing |
| Defines scope | What is and is **not** covered: the study's boundaries, limitations, or explicit inclusions and exclusions | Preface: Defines Scope Missing |

Take the elements one at a time, in the order above, and for each find the preface sentence that states it. An element is present only when you can point to such a sentence; an element you cannot tie to a sentence is missing, however well the rest of the preface reads. Do not let a strong preface carry an element it never states.

In each issue's description, say in 1–3 sentences what you looked for and what the preface says instead. The suggested action should tell the author what this report's preface should add, drawing on the rest of the report (the readers its findings address, the aims its methods reveal, the boundaries its analysis actually has), not advice that would fit any report.

## 3 — About the Authors

Locate the author biographies: the section that satisfied About the Authors in part 1. Identify each biography, typically a separate paragraph per person; ignore paragraphs shorter than about 50 characters, which are not biographies.

Evaluate **each** biography against every rule below:

1. **Sentence count.** The biography has **exactly three sentences**. Abbreviations with periods (Ph.D., M.D., J.D., M.S., B.S., M.A., B.A., Dr., Mr., Ms., e.g., i.e., etc.) do not end a sentence.
2. **Position and affiliation.** It states the author's current **position** (senior researcher, policy analyst, professor) and **institutional affiliation** (RAND, a university, a government agency). Both are required.
3. **Research focus.** It describes the author's research focus, interests or area of expertise.
4. **Highest degree.** It names the author's highest academic degree (Ph.D., M.A., M.D., J.D.). A title such as "Dr." alone does not name a degree.

For each biography that fails any rule, report **one** issue titled **"Author Bio Issue: {author_name}"**, with the author's full name as it appears in the biography, and **severity: medium**. Place the issue on the biography. Its description lists every rule the biography fails, and only those. Its suggested action says, for this author, which element to add or which sentence to cut or merge to reach three sentences; it must not supply a degree, institution, position or research area the report does not state. Report nothing for a biography that passes every rule.

## Reporting

Report findings following the conventions in the `issues` skill, with the exact titles and severities given above. Do not report issues for rules that pass.

When you also write a summary report, give it a checklist for each part: every required section as present or missing, each of the six preface elements as PASS or FAIL with the sentence that satisfies it, and each author's four rules as PASS or FAIL. Every FAIL in the checklist has a matching issue.
