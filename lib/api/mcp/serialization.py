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


def build_gate_required_payload(exc: WorkflowGateRequiredError) -> dict:
    """Build the JSON payload returned to the MCP client when consent is missing."""
    pending_human_approval = [w.value for w in exc.pending_human_approval]
    pending_web_search = [w.value for w in exc.pending_web_search]

    retry_flags: list[str] = []
    if pending_human_approval:
        retry_flags.append("approve_human_steps=true")
    if pending_web_search:
        retry_flags.append("approve_web_search=true")
    retry_flags_text = " and ".join(retry_flags)

    sections: list[str] = []
    if pending_human_approval:
        sections.append(
            "Human approval is required because the user must review the "
            "reference→file mappings before these workflows can run: "
            f"{pending_human_approval}. Share the project_url with the user "
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
            "  \"To run this assessment, parts of your document — and possibly "
            "the whole document — will be sent to a web search provider as "
            "search queries. Don't proceed if the document contains "
            "confidential information you aren't comfortable sharing with an "
            "external search engine. Do you consent to running web search on "
            "this document?\"\n\n"
            "Only retry with approve_web_search=true after the user "
            "explicitly consents. If they decline, do not retry — instead "
            "offer to run a different workflow that doesn't need web access "
            "(see list_workflow_types and skip any with needs_web_search=true)."
        )
    sections.append(
        "Once the user confirms (e.g. 'go ahead and start'), call "
        f"run_workflow again with the same arguments plus {retry_flags_text}."
    )

    return {
        "status": "approval_required",
        "project_id": exc.project_id,
        "project_url": build_project_url(exc.project_id),
        "pending_human_approval": pending_human_approval,
        "pending_web_search": pending_web_search,
        "message": "\n\n".join(sections),
    }
