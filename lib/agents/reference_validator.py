from __future__ import annotations

from enum import Enum
from typing import List, Optional

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_4_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class FieldProblemType(str, Enum):
    CORRECT = "correct"
    MISSING = "missing"
    INCORRECT = "incorrect"
    OTHER = "other"


class FieldCategory(str, Enum):
    AUTHOR = "author"
    TITLE = "title"
    PUBLISHER = "publisher"
    YEAR = "year"
    IDENTIFIER = "identifier"


class BibliographyFieldValidation(BaseModel):
    category: FieldCategory = Field(
        description=f"Category of the reference. Possible values: {[e.value for e in FieldCategory]}"
    )
    current_value: str = Field(description="Current value of the reference.")
    suggested_value: str = Field(description="Suggested value of the reference.")
    problem_type: FieldProblemType = Field(
        description=f"Problem type of the reference. Must be CORRECT if the only differences are capitalization or minor punctuation. Possible values: {[e.value for e in FieldProblemType]}"
    )


class ReferenceValidationFinalResult(str, Enum):
    VALID = "valid"
    FOUND_WITH_INCONSISTENCIES = "found_with_inconsistencies"
    NOT_FOUND = "not_found"


class BibliographyItemValidation(BaseModel):
    original_reference: str = Field(description="Original bibliographic item text.")
    final_result: ReferenceValidationFinalResult = Field(
        description=f"Overall validation outcome. Possible values: {[e.value for e in ReferenceValidationFinalResult]}"
    )
    bibliography_field_validations: List[BibliographyFieldValidation] = Field(
        description="List of reference field validations."
    )
    suggested_action: str = Field(
        description="Suggested action to take if the reference is not valid. A summary of the suggested changes to make the reference valid. If the reference is valid, return 'No changes needed'."
    )
    url: str = Field(description="Found URL for the reference.")
    reasoning: str = Field(
        default="",
        description="Step-by-step reasoning describing your approach to validate the reference.",
    )
    updated_reference: Optional[str] = Field(
        default=None,
        description="Updated reference with the suggested changes made to make the reference valid, matching the format of the original reference. If the reference is already valid, return null.",
    )


SYSTEM_PROMPT = """Validate a single bibliographic reference by finding the cited work online and comparing it to the reference. The next message contains the reference to validate — follow the six-step procedure below.

# Step 1 — Parse the reference

Read the reference and note:
- What type of work it is (journal article, preprint, book, webpage, press release, government report, briefing slides, etc.).
- Which fields are present: author, title, publisher/venue, year, identifier (DOI, arXiv ID, ISBN, ISSN), URL.

Special case — bare URL: if the reference is only a URL with no bibliographic metadata, skip ahead to Step 6 with final_result `found_with_inconsistencies`. Reconstruct the full citation from the URL's content and populate `updated_reference`. Mark all five field validations as MISSING except `identifier`, which may be the URL itself or MISSING.

# Step 2 — Resolve the URL (if the reference contains one)

Fetch the URL exactly as given. One of three outcomes:

- URL resolves to real content that appears to match the reference → use that page as your primary authoritative source. Continue to Step 4.
- URL resolves but the page is clearly unrelated (a different article, a generic landing page) → note the URL as inconsistent. Continue to Step 3 to search.
- URL returns 404 or error → the URL is inconsistent or fabricated. Continue to Step 3.

Do NOT treat a URL as valid just because its domain/path looks plausible — you must confirm the page actually exists and has real content.

# Step 3 — Search the web for the cited work

Search using the reference's title (quote distinctive phrases) together with a key author surname and/or year. For references with a DOI or arXiv ID, resolve the identifier first and use the canonical page — BUT if the resolved work's title clearly does not match the reference's title, treat the identifier as incorrect or fabricated and search by title instead. Do NOT accept an unrelated work as your candidate just because an identifier happened to resolve to it; when this happens, flag the identifier as INCORRECT in Step 5 and use the title-based candidate for the other fields.

Pick the single best candidate that plausibly IS the cited work. If no candidate matches the cited title or authors, stop and go to Step 6 with `not_found`.

ArXiv-specific rules:
- ArXiv versioning: when the reference cites an arXiv paper WITHOUT a version suffix (e.g., `arXiv:2311.16169` rather than `arXiv:2311.16169v1`), treat the MOST RECENT version on arXiv as authoritative — its title, author list, and most-recent submission year. When the reference explicitly pins a version (e.g., `arxiv.org/abs/2406.01637v1`), treat that version as authoritative instead.
- ArXiv HTML view: URLs of the form `arxiv.org/html/...` sometimes contain rendering artifacts that produce incorrect-looking titles. Do not take the title from the HTML view. Prefer, in order: (a) the title from the official conference/journal publication if one exists, (b) the arXiv abstract page `arxiv.org/abs/...`, (c) the PDF.
- ArXiv + official publication: if a paper has both an arXiv preprint and an official conference/journal publication (e.g., IEEE S&P, ACM CSCW, NeurIPS), the official venue is the preferred publisher; the arXiv ID remains a valid identifier.

# Step 4 — Decide whether the candidate is the same work

Before comparing fields, confirm the candidate source IS the cited work. Compare the candidate's title to the reference's title, ignoring case and punctuation:

- Titles match in wording → it is the SAME WORK. Proceed to Step 5. (Any disagreements in author, publisher, or year are attribution errors in the citation, not a mis-match.)
- Titles clearly differ in wording AND two or more of {author, publisher, year} also differ → the candidate is a DIFFERENT WORK on a related topic. Go to Step 6 with `not_found`. Do not try to "rescue" a bad reference by treating a different work as a match.
- Titles differ but author, publisher, and year all line up → likely the same work under a retitling or reprinting. Treat as same work and continue to Step 5.

# Step 5 — Compare each field

For each of author, title, publisher, year, identifier, set `problem_type`:

- CORRECT — the reference matches the authoritative source in substance. Apply CORRECT when the only differences are:
  * Capitalization (title case vs sentence case vs all caps)
  * Punctuation (commas, periods, hyphens/dashes, colons, quotation marks, trailing separators)
  * Author name form (full first name vs initial, middle initial present/absent, surname particles like "von"/"de"/"van" present/absent)
  * Truncated author lists (the reference lists the first N authors, with or without "et al.", while the full work has more authors — this is a valid citation style, not an error)
  * Organization form (well-known abbreviation vs full name — e.g., "ACM" = "Association for Computing Machinery", "DMDC" = "Defense Manpower Data Center"; current brand vs recent rebrand — e.g., "Raytheon Technologies" = "RTX")
  * Field ordering
  * Page ranges (ignore entirely)
- MISSING — the field is absent from the reference but exists for the work.
- INCORRECT — the reference contains substantively different content: different words, different people, wrong numbers, wrong dates, historically incorrect names (e.g., a pre-1947 government title used to cite a modern agency).

Field-specific notes:
- Title: use the title that appears in the main content body of the authoritative page — the `<h1>` heading, the article headline, or the title page of a PDF. Do NOT use the browser tab `<title>` tag, the `og:title` social-sharing title, or a search-engine snippet — these are often shortened or sanitized. For PDF-linked articles, prefer the title inside the PDF.
- Identifier: a DOI, arXiv ID, ISBN, or ISSN all qualify. If the reference includes one, check it resolves to the correct work. Accept equivalent forms: a URL that resolves to a persistent identifier (e.g., `https://doi.org/10.xxxx/...`, `https://dl.acm.org/doi/pdf/10.xxxx/...`, `https://arxiv.org/abs/...`) is equivalent to the bare identifier — do NOT flag the URL form as INCORRECT just because the bare DOI or arXiv ID is the canonical form. If the reference omits an identifier but one exists, mark MISSING. If no identifier exists at all, mark CORRECT with empty values. A missing DOI when an arXiv ID is already present is NOT an error.
- Author for institutional works: when the publishing organization is listed as the author (press releases, homepages, government reports, briefing slides, datasets, policy directives), the org name is the author. Do not demand a list of individuals.

# Step 6 — Decide the final result

Apply in order:

1. No candidate found, OR candidate is a different work (per Step 4) → `final_result = "not_found"`. Set `updated_reference = null`.
2. Same work, zero INCORRECT fields, and no MISSING key fields (title, author) → `final_result = "valid"`. Set `updated_reference = null`.
3. Same work, at least one INCORRECT field or a MISSING key field → `final_result = "found_with_inconsistencies"`. Populate `updated_reference` with the corrections applied, preserving the reference's original citation style.

When you are on the boundary between `valid` and `found_with_inconsistencies`, default to `valid`. Only escalate to `found_with_inconsistencies` when the errors would mislead a reader or make the work hard to locate. Specifically, these remain `valid`:
- A missing identifier when the reference has a resolving URL or clear venue
- Minor name-form variations covered by the CORRECT rules above
- Slight title wording differences that do not change meaning
- A missing publisher/venue when it is obvious from the rest of the citation

Reserve `found_with_inconsistencies` for substantive errors: wrong author names, a factually wrong title (different words), wrong year, a DOI or URL that resolves to a different work.

# Output fields

- `original_reference` — the reference as given.
- `final_result` — `valid` / `found_with_inconsistencies` / `not_found`.
- `bibliography_field_validations` — one entry per field with `current_value`, `suggested_value`, `problem_type`.
- `url` — the URL identifying the cited work (from the reference, identifier resolution, or your search). Empty string when `not_found`.
- `reasoning` — a brief step-by-step summary of how you validated.
- `suggested_action` — one sentence describing what to fix; `"No changes needed"` when `valid`.
- `updated_reference` — corrected citation in the reference's original format when `found_with_inconsistencies`; otherwise `null`.

# Response hygiene

Never include internal search tokens (e.g., `turn0search0`) or raw metadata markers in any output field. All text must be clean and human-readable."""


class ReferenceValidatorAgent(LangChainAgent):
    name = "Reference Validator"
    description = "Validate a list of references in a document, by searching for their online presence."
    model = gpt_5_4_model
    temperature = 0.0
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[BibliographyItemValidation, list[BaseMessage]]:
        agent = create_agent(
            self.llm,
            [{"type": "web_search"}],
            context_schema=ContextSchema,
            response_format=BibliographyItemValidation,
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=prompt_kwargs["reference"]),
                ]
            },
            config=config,
            context=self.context,
        )

        return result["structured_response"], result["messages"]
