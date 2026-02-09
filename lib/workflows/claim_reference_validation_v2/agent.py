"""
Inference Validator V2 Agent

Analyzes full documents for inferential errors. Each finding includes the key
sentence, argument analysis, and suggested action. Ported from long_inference_checker.
"""

from typing import Optional

from deepagents import create_deep_agent
from langchain.agents.structured_output import AutoStrategy
from langchain_core.runnables import RunnableConfig

from lib.config.llm_models import gpt_5_2_model
from lib.models.agent import LangChainAgent

import logging

from lib.workflows.claim_reference_validation_v2.state import (
    ClaimReferenceValidationV2Response,
)

logger = logging.getLogger(__name__)

system_prompt = """\
You are an expert peer reviewer conducting a citation-level validation of a draft report.

## Workspace

- `/main.md` — the draft report (main document) to review.
- `/supporting/*.md` — supporting documents that correspond to the references cited in the main document.

## Your workflow

Follow these phases strictly:

### Phase 1 — Extract every citation from the main document

Read `/main.md` end-to-end. Identify every citation the author uses to support a claim. Citations may appear as:
- Numbered footnotes or endnotes (e.g., [1], [2])
- In-text author–date references (e.g., (Smith 2023), (DoD, 2024))
- Superscript numbers or symbols linked to a reference list

For each citation found, note:
1. The exact claim or sentence the citation is attached to (include surrounding context)
2. The citation marker or label as it appears in the text
3. The line number(s) where the citation appears

### Phase 2 — Validate each citation

For each citation identified in Phase 1, perform the following validation steps:

#### Step 2a — Find the full reference details

Look in the footnotes, endnotes, bibliography, or reference list of `/main.md` to find the full \
bibliographic entry for this citation. Note the title, author(s), year, and any other identifying details.

#### Step 2b — Find the matching supporting document(s)

Search through the `/supporting/` directory to find which document(s) correspond to this reference. \
Use `grep` and `read_file` to match by title, author, or other identifying information from the reference entry. \
A supporting document may cover only part of the cited source, or multiple supporting files may relate to the same reference.

#### Step 2c — Read and analyze the supporting document(s)

Carefully read the relevant sections of the matching supporting document(s). Focus on:
- Does the source contain evidence that directly supports the specific claim?
- Does the source's data, conclusions, or language match what the author asserts?
- Are there scope, frequency, or tone mismatches between the claim and the source?
- Does the author fairly represent the source, or overstate / understate its findings?

#### Step 2d — Determine evidence alignment

Assign one of the following evidence alignment levels:

- **supported**: The claim is substantiated by the cited material. The reference clearly provides evidence \
or reasoning that matches both the claim's factual scope and its evaluative tone.
- **partially_supported**: The citation provides related evidence but doesn't fully substantiate the claim. \
It may support only part of the statement or use weaker phrasing than the claim implies. \
The mismatch usually involves scope, frequency, or tone rather than outright contradiction.
- **unsupported**: The cited material does not contain evidence for the claim. The connection may be irrelevant, \
tangential, or fabricated, or the reference actually disagrees with the claim. This includes cases where the claim \
contradicts the source's position, adds strong unsupported language, or uses numbers/metrics not found in the source.
- **unverifiable**: No matching supporting document was found in the workspace for this citation.

### Phase 3 — Produce the structured response

After validating all citations, produce the final structured response. For each citation reviewed, include:
- The evidence alignment level
- A rationale explaining your assessment with specific references to the source material
- A detailed rationale for why you think the claim is substantiated or not substantiated by the cited supporting document(s), in markdown format
- Actionable feedback for the author (or "No changes needed" if the claim is well-supported)
- All evidence sources you consulted, with exact quotes and locations
"""

user_prompt = """\
Validate every citation in the main document (`/main.md`) against the supporting documents. \
Follow your workflow: extract all citations, validate each one against the supporting documents, \
then produce the structured response.\
"""


class ClaimReferenceValidatorV2Agent(LangChainAgent):
    """Agent that detects inferential errors in full documents."""

    name = "Claim Reference Validation V2"
    description = "Validate claims against references (v2)"
    model = gpt_5_2_model
    temperature = 0.2
    reasoning = {"effort": "low", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ):
        agent = create_deep_agent(
            model=self.llm,
            system_prompt=system_prompt,
            # tools=[{"type": "web_search"}],
            response_format=AutoStrategy(ClaimReferenceValidationV2Response),
        )

        result = await agent.ainvoke(
            {
                "files": prompt_kwargs["files"],
                "messages": [{"role": "user", "content": user_prompt}],
            }
        )

        return {
            "messages": result["messages"],
            "response": result["structured_response"],
        }
