"""Manifest for the Figures and Tables Check workflow.

Validates that every figure and table in the document is consistent:
- Every figure/table is mentioned in the body text.
- Every figure/table mentioned in the body has an associated image/table present.
- Every figure/table has a title/caption.
- All figures/tables are numbered sequentially or by chapter.
"""

from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.manifest_base import SimpleDeepAgentManifest

_USER_PROMPT = """\
Evaluate the document against **every** rule below.
For each rule that **fails**, report one issue.
For rules that pass, do **not** create an issue.

---

## Rules

### Rule 1 — Every figure/table has a title or caption

Every figure and every table in the document must have a descriptive title
or caption directly associated with it.
Look for labels such as "Figure X:", "Fig. X:", "Table X:" followed by a
caption or title string.

**If any figure or table has no title or caption → issue title:**
"Figure/Table Missing Title: [label]"
(Create one issue per offending figure/table.)

---

### Rule 2 — All figures and tables are numbered consistently

All figures must follow one numbering scheme throughout the document, and
all tables must follow one numbering scheme throughout the document.

Accepted schemes (either is valid; mixing within the same element type is
not):

- **Sequential**: Figure 1, Figure 2, Figure 3 … (or Table 1, Table 2 …)
  Supplementary items may be numbered separately as Figure S1, S2 …
  or Table S1, S2 …
- **By chapter**: Figure 4.1, Figure 4.2 … (or Table 4.1, Table 4.2 …
  where the first digit is the chapter number)

Flag the document if:
- Numbering skips values without explanation (e.g. Figure 1, Figure 3 with
  no Figure 2 anywhere)
- Two different schemes are mixed within the same element type (e.g.
  Figure 1, Figure 2, Figure 3.1)
- A figure or table has no number at all

**If inconsistent numbering is found → issue title:**
"Inconsistent Numbering: [brief description]"

---

### Rule 3 — Every figure/table is referenced in the body text

Every figure and table that appears in the document must be cited at least
once in the body text (e.g. "see Figure 3", "as shown in Table 2",
"(Table S1)").
Cross-references in captions of other figures/tables do not count as body
text references.

**If a figure or table is never mentioned in the body → issue title:**
"Unreferenced Figure/Table: [label]"
(Create one issue per unreferenced figure/table.)

---

### Rule 4 — Every figure/table mentioned in the body is present in the document

Every figure and table cited in the body text must actually exist in the
document.  Check that each reference of the form "Figure X", "Fig. X",
"Table X" etc. has a corresponding labelled figure or table.

**If a referenced figure/table is absent from the document → issue title:**
"Missing Figure/Table: [label referenced in text]"
(Create one issue per missing figure/table.)

"""


class FiguresTablesCheckManifest(SimpleDeepAgentManifest):
    """Checks figures and tables for consistency across the document."""

    type = WorkflowRunType.FIGURES_TABLES_CHECK
    name = "Figures & Tables Check"
    description = (
        "Checks that every figure and table has a title, is consistently numbered, "
        "is referenced in the body text, and that all body-text references resolve "
        "to an actual figure or table in the document."
    )
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    is_experimental = True

    user_prompt = _USER_PROMPT
