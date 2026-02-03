import asyncio
from lib.workflows.runner import run_workflow_from_config
from lib.models.workflow_run import WorkflowRunStatus
from lib.workflows.registry import create_state
from lib.workflows.models import WorkflowRunType
from lib.workflows.inference_validation_v2.state import (
    InferenceValidationV2WorkflowConfig,
)
from lib.services.workflow_runs import (
    create_workflow_run,
    get_project_workflow_run_by_type,
    get_thread_id_for_workflow_run,
)
from lib.services.users import get_or_create_user_by_email
from lib.services.projects import get_user_project

PROJECT_ID = "54190efa-3919-43ce-a6fb-8fba1dfff8d1"


async def main():
    # Get or create user
    user = await get_or_create_user_by_email("mobolaji@ae.studio", name="")

    # Confirm project exists and belongs to user
    project = await get_user_project(PROJECT_ID, user)

    # ensure processing state exists
    run_type = await get_project_workflow_run_by_type(
        PROJECT_ID, WorkflowRunType.INFERENCE_VALIDATION_V2
    )

    # Build config
    config = InferenceValidationV2WorkflowConfig(
        type=WorkflowRunType.INFERENCE_VALIDATION_V2, project_id=PROJECT_ID
    )

    # get existing run
    existing_run = await get_project_workflow_run_by_type(
        PROJECT_ID, WorkflowRunType.INFERENCE_VALIDATION_V2
    )

    # reuse existing inference validation thread
    thread_id = get_thread_id_for_workflow_run(existing_run)

    # getting workflow run id
    workflow_run_id = await create_workflow_run(
        project_id=PROJECT_ID,
        status=WorkflowRunStatus.PENDING,
        type=WorkflowRunType.INFERENCE_VALIDATION_V2,
        thread_id=thread_id,
    )

    # running workflow
    final_state = await run_workflow_from_config(
        config=config, thread_id=thread_id, workflow_run_id=workflow_run_id, user=user
    )

    print("Initial Inference Results")
    if hasattr(final_state, "inference_results") and final_state.inference_results:
        print(len(final_state.inference_results.results), "Results")
        for r in final_state.inference_results.results:
            print(r.key_sentence, r.inference_validity)
    if final_state.errors:
        print("Final State Errors", final_state.errors)
    print()

    # printing inference results
    print(final_state.inference_results)

    # Optionally print project details to confirm correct user/project association
    print("User:", user)
    print("Project:", project)


if __name__ == "__main__":
    asyncio.run(main())
