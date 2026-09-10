import json

from lib.api.mcp.helpers import build_project_url
from lib.api.services.workflow_runner import WorkflowGateRequiredError
from lib.models.project import AccessLevel
from lib.models.user import User
from lib.services.projects import (
    get_project_access,
    get_project_detailed_from_project,
)


async def get_project_details_json(
    project_id: str,
    access_level: AccessLevel,
    user: User,
    revision: int | None = None,
) -> str:
    """Fetch project details and return as JSON, excluding files and feedbacks."""
    project, _ = await get_project_access(
        project_id, user=user, required_level=access_level
    )
    project_detailed = await get_project_detailed_from_project(
        project=project,
        access_level=access_level,
        include_internal=True,
        revision=revision,
    )
    data = project_detailed.model_dump(mode="json", exclude={"files", "feedbacks"})
    data["project_url"] = build_project_url(project_id)
    return json.dumps(data)


# The one wording every surface uses to ask for web-search consent: this gate
# relays it, and the portable skills under `skills/` quote it for the agents
# that run a check without the app in front of them. Keep the two in step —
# tests/unit/test_skills.py compares them.
WEB_SEARCH_CONSENT_QUESTION = (
    "To run this assessment, parts of your document — and possibly the whole "
    "document — will be sent to a web search provider as search queries. "
    "Don't proceed if the document contains confidential information you "
    "aren't comfortable sharing with an external search engine. Do you "
    "consent to running web search on this document?"
)


def build_gate_required_payload(exc: WorkflowGateRequiredError) -> dict:
    """Build the JSON payload returned to the MCP client when consent is missing."""
    pending_human_approval = [w.value for w in exc.pending_human_approval]
    pending_web_search = [w.value for w in exc.pending_web_search]
    # The exact list to pass on the retry. Up front (nothing started) it is the
    # original request; mid-flight it is only the workflows held back by a
    # gate, since everything else already ran on this call.
    retry_workflow_types = [w.value for w in exc.retry_workflow_types]

    retry_flags: list[str] = []
    if pending_human_approval:
        retry_flags.append("approve_human_steps=true")
    if pending_web_search:
        retry_flags.append("approve_web_search=true")
    retry_flags_text = " and ".join(retry_flags)

    completed_workflows = [w.value for w in exc.completed_workflows]
    unsuccessful_workflows = {
        w.value: status.value for w, status in exc.unsuccessful_workflows.items()
    }

    if exc.nothing_started:
        opening = (
            "No workflow has been started yet: consent is required before "
            "anything runs on this document."
        )
    else:
        opening = (
            "The workflows that did not need consent have already run on this "
            f"call. Completed: {completed_workflows}."
        )
        if unsuccessful_workflows:
            opening += (
                f" Did NOT complete: {unsuccessful_workflows}. Tell the user "
                "these analyses failed; they produced no results. They can be "
                "run again by including them in workflow_types on the retry."
            )
        opening += " Only the gated workflows listed below are still pending."
    sections: list[str] = [opening]
    if pending_human_approval and exc.nothing_started:
        sections.append(
            "Human approval will also be required for these workflows, because "
            "the user must review the reference→file mappings before they run: "
            f"{pending_human_approval}. You can ask for that consent now "
            "together with the web-search consent and pass "
            "approve_human_steps=true on the retry. If the user prefers to "
            "review the references first, retry with approve_web_search=true "
            "only: the upstream analysis will run, these workflows will wait in "
            "awaiting_approval, and the response will point you at the "
            "references to review before approving."
        )
    elif pending_human_approval:
        sections.append(
            "Human approval is required because the user must review the "
            "reference→file mappings before these workflows can run: "
            f"{pending_human_approval}. Those assessments are awaiting approval; "
            "approving it (here via approve_human_steps=true, or in the web "
            "UI) starts them. Share the project_url with the user "
            "so they can review references in the web UI, or offer to list "
            "the references and supporting-file mappings here (use "
            "get_project to fetch them).\n\n"
            "Offer the user these options for filling in missing supporting "
            "files before approving:\n"
            "  1. Have Draft Detective auto-fetch them from the web — add "
            "'reference_downloader' to workflow_types on the retry call "
            "(this also requires approve_web_search=true).\n"
            "  2. Provide/upload the files yourself — call "
            "get_tus_upload_credentials with role='support' and the matching "
            "reference_id (from get_project) for each file, then upload via "
            "the returned TUS endpoint before retrying."
        )
    if pending_web_search:
        sections.append(
            "Web-search consent is required for these workflows: "
            f"{pending_web_search}. Before retrying, relay the following to "
            "the user verbatim and get their explicit OK:\n\n"
            f'  "{WEB_SEARCH_CONSENT_QUESTION}"\n\n'
            "Only retry with approve_web_search=true after the user "
            "explicitly consents. If they decline, do not retry — instead "
            "offer to run a different workflow that doesn't need web access "
            "(see list_workflow_types and skip any with needs_web_search=true)."
        )
    closing = (
        "Once the user confirms (e.g. 'go ahead and start'), call "
        f"run_workflow again with workflow_types={retry_workflow_types} "
        f"(the retry_workflow_types field) plus {retry_flags_text}."
    )
    if not exc.nothing_started:
        closing += (
            " Do NOT resend the workflow types that completed: every type "
            "passed explicitly is run again, which duplicates their issues and "
            "doubles the cost and wait."
        )
    sections.append(closing)

    return {
        "status": "approval_required",
        "project_id": exc.project_id,
        "project_url": build_project_url(exc.project_id),
        "pending_human_approval": pending_human_approval,
        "pending_web_search": pending_web_search,
        "retry_workflow_types": retry_workflow_types,
        "completed_workflows": completed_workflows,
        "unsuccessful_workflows": unsuccessful_workflows,
        "message": "\n\n".join(sections),
    }
