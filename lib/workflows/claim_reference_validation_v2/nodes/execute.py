from typing import Any, Dict

from deepagents.backends.state import create_file_data
from langgraph.runtime import Runtime

from lib.workflows.claim_reference_validation_v2.agent import (
    ClaimReferenceValidatorV2Agent,
)
from lib.workflows.claim_reference_validation_v2.state import (
    ClaimReferenceValidationV2State,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node


@register_node("Execute", "Execute claim reference validation v2")
async def execute(
    state: ClaimReferenceValidationV2State, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    """Execute claim reference validation v2."""

    # Load files from service
    file_artifacts_service = runtime.context.file_artifacts_service
    main_file = await file_artifacts_service.get_main_file()
    supporting_files = await file_artifacts_service.get_supporting_files()

    # Build pre-populated files dict for StateBackend
    files: Dict[str, Any] = {"/main.md": create_file_data(main_file.markdown)}
    for f in supporting_files:
        files[f"/supporting/{f.file_id}.md"] = create_file_data(f.markdown)

    agent = ClaimReferenceValidatorV2Agent(runtime.context)
    return await agent.ainvoke({"files": files})
