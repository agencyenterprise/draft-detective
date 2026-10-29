"""Per-run inputs for the deep agents that search the web against a bibliography.

Literature Review and Live Reports both append the document's publication date
and its extracted bibliography to their skill prompt; they differ only in how
the bibliography is introduced.
"""

from datetime import date

from lib.agents.formatting_utils import format_bibliography
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.workflows.simple_deep_agent.state import SimpleDeepAgentState

_INPUTS_TEMPLATE = """\

---

## Inputs for this run

### Document publication date
{document_publication_date}

### {bibliography_heading}
```
{bibliography}
```
"""


async def bibliography_inputs(
    state: SimpleDeepAgentState,
    service: FileArtifactsServiceType,
    bibliography_heading: str,
) -> str:
    """The publication date (today when unset) and the extracted bibliography."""
    references = await service.get_extracted_references()
    return _INPUTS_TEMPLATE.format(
        document_publication_date=state.config.publication_date
        or date.today().isoformat(),
        bibliography_heading=bibliography_heading,
        bibliography=format_bibliography(references),
    )
