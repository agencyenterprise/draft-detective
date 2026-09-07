"""Async HTTP client for calling the Draft Detective API in e2e evals."""

import asyncio
import base64
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt

from evals_inspectai.common.errors import (
    WorkflowCompletionError,
    check_workflow_errors,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_USER_EMAIL = "eval@draft-detective.local"
DEFAULT_USER_NAME = "E2E Eval Runner"
DEFAULT_POLL_INTERVAL_S = 5
DEFAULT_TIMEOUT_S = 300

JWT_ALGORITHM = "HS512"
JWT_ISSUER = "ai-reviewer"
JWT_AUDIENCE = "ai-reviewer-api"

# The dev server runs workflow agents in-process, so a routine GET can sit
# behind them when several are running at once.
DEFAULT_HTTP_TIMEOUT_S = 300.0

TUS_VERSION = "1.0.0"

# `FileRole` values, as the app sends them in the TUS upload metadata.
MAIN_ROLE = "main"
SUPPORT_ROLE = "support"

# Run statuses from which a workflow can never reach "completed".
TERMINAL_FAILURE_STATUSES = frozenset({"failed", "cancelled"})


def _get_base_url() -> str:
    return os.environ.get("EVAL_API_BASE_URL", DEFAULT_BASE_URL)


def _get_auth_token() -> str:
    """Return a Bearer token, either from env or by minting one with AUTH_SECRET."""
    token = os.environ.get("EVAL_API_AUTH_TOKEN")
    if token:
        return token

    secret = os.environ.get("AUTH_SECRET")
    if not secret:
        raise RuntimeError(
            "Set EVAL_API_AUTH_TOKEN (pre-minted JWT) or AUTH_SECRET "
            "(to auto-generate one) before running e2e evals."
        )

    payload = {
        "email": os.environ.get("EVAL_USER_EMAIL", DEFAULT_USER_EMAIL),
        "name": os.environ.get("EVAL_USER_NAME", DEFAULT_USER_NAME),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=_get_base_url(),
        headers={"Authorization": f"Bearer {_get_auth_token()}"},
        timeout=DEFAULT_HTTP_TIMEOUT_S,
    )


async def create_project(title: str) -> str:
    """Create an empty project and return its id."""
    async with _build_client() as client:
        resp = await client.post("/api/projects", json={"title": title})
        resp.raise_for_status()
        project_id = str(resp.json()["project"]["id"])

    logger.info("Created project %s", project_id)
    return project_id


async def set_publication_date(project_id: str, publication_date: str) -> None:
    """Set a project's document publication date (YYYY-MM-DD).

    Date-sensitive workflows (live reports, literature review) read the date off
    the project when their config is built, so it has to be set before the
    workflows are started. This is also how the app sets it, from the analysis
    options menu.
    """
    async with _build_client() as client:
        resp = await client.patch(
            f"/api/project/{project_id}",
            json={"publication_date": publication_date},
        )
        resp.raise_for_status()

    logger.info("Set publication_date=%s on project %s", publication_date, project_id)


async def create_project_and_start_workflows(
    file_content: str,
    workflow_types: list[str],
    file_name: str = "document.md",
    supporting_files: list[tuple[str, str | Path]] | None = None,
    publication_date: str | None = None,
) -> str:
    """Create a project, upload its documents, and start workflows on it.

    This is the same sequence the app performs when a user starts an
    assessment: `POST /api/projects`, upload each document through TUS, then
    `POST /api/workflows/start-multiple`. Keeping the eval on those endpoints
    means a break in the path real users take shows up here too.

    Args:
        file_content: Markdown content of the main document.
        workflow_types: Workflow types to trigger (dependencies are auto-resolved
            server-side; pass only the leaf workflow).
        file_name: Display name for the main document, also used as the project
            title, as the app does.
        supporting_files: Optional list of (file_name, content_or_path) tuples
            uploaded alongside the main document with the SUPPORT role. The
            second element can be either:
              - a markdown string, or
              - a `Path` pointing at an existing file (e.g. a PDF), whose bytes
                are uploaded as-is.
        publication_date: Optional document publication date (YYYY-MM-DD). Used
            by date-sensitive workflows such as live reports, which search for
            sources published after this date.

    Returns the project_id.
    """
    project_id = await create_project(title=file_name)

    if publication_date:
        await set_publication_date(project_id, publication_date)

    await tus_upload_file(
        project_id=project_id,
        file_name=file_name,
        content=file_content,
        role=MAIN_ROLE,
    )

    for sf_name, sf_value in supporting_files or []:
        await tus_upload_file(
            project_id=project_id,
            file_name=sf_name,
            content=sf_value.read_bytes() if isinstance(sf_value, Path) else sf_value,
            role=SUPPORT_ROLE,
        )

    await start_workflow_types(project_id, workflow_types)
    return project_id


def _encode_tus_metadata(metadata: dict[str, str]) -> str:
    """Encode upload metadata as the TUS `Upload-Metadata` header value."""
    return ",".join(
        f"{key} {base64.b64encode(value.encode()).decode()}"
        for key, value in metadata.items()
    )


async def tus_upload_file(
    project_id: str,
    file_name: str,
    content: str | bytes,
    role: str,
    revision: int | None = None,
) -> None:
    """Upload a file into an existing project through the TUS endpoint.

    This is the only upload path the app has, and the only one that reads a
    `role` (and, for the revision-scoped roles, a `revision`) from the upload
    metadata.

    Args:
        project_id: Project to attach the file to.
        file_name: Display name for the uploaded file.
        content: File content, either text or raw bytes (e.g. a PDF).
        role: A `FileRole` value, e.g. "main", "support" or "reviewer_memo".
        revision: Revision the file belongs to. Only meaningful for the
            revision-scoped roles (main, reviewer_memo); omitting it attaches
            the file to the project's current revision.

    The upload is done as a create (POST) followed by a single write (PATCH).
    The creation-with-upload shortcut is deliberately not used: tuspyserver
    only fires the completion hook that creates the file record from the PATCH
    route, so a POST carrying the whole body would upload bytes and never
    register the file.
    """
    payload = content.encode() if isinstance(content, str) else content
    metadata = {"filename": file_name, "project_id": project_id, "role": role}
    if revision is not None:
        metadata["revision"] = str(revision)

    async with _build_client() as client:
        create = await client.post(
            "/tus",
            headers={
                "Tus-Resumable": TUS_VERSION,
                "Upload-Length": str(len(payload)),
                "Upload-Metadata": _encode_tus_metadata(metadata),
            },
        )
        create.raise_for_status()

        # The Location header is absolute; the client is already bound to the
        # API base URL, so only its path is needed.
        upload_path = urlparse(create.headers["Location"]).path

        write = await client.patch(
            upload_path,
            content=payload,
            headers={
                "Tus-Resumable": TUS_VERSION,
                "Upload-Offset": "0",
                "Content-Type": "application/offset+octet-stream",
            },
        )
        write.raise_for_status()
        logger.info(
            "Uploaded %s (role=%s, revision=%s) to project %s",
            file_name,
            role,
            revision,
            project_id,
        )


async def link_reference_file(project_id: str, reference_id: str, file_id: str) -> None:
    """Link an already-uploaded supporting file to an extracted reference.

    Records a MANUAL_UPLOAD match, the same one the app creates when a user
    supplies the source for a reference themselves. Use it when the correct
    reference->file pairing is known up front and running the automatic matcher
    would only add noise.
    """
    async with _build_client() as client:
        resp = await client.post(
            f"/api/project/{project_id}/references/{reference_id}/files",
            json={"file_id": file_id},
        )
        resp.raise_for_status()

    logger.info(
        "Linked file %s to reference %s on project %s",
        file_id,
        reference_id,
        project_id,
    )


async def approve_project_gate(project_id: str, gate: str = "reference_review") -> None:
    """Approve a gate for the project's current revision, the same call the
    web UI's Approve button makes. Releases every run waiting on that gate."""
    async with _build_client() as client:
        resp = await client.post(f"/api/projects/{project_id}/gates/{gate}/approve")
        resp.raise_for_status()
        logger.info("Approved gate=%s for project %s", gate, project_id)


async def find_workflow_run_by_type(
    project_id: str, workflow_type: str
) -> dict[str, Any] | None:
    """Return the most recent run-detail dict for the given workflow type, or None."""
    project = await get_project_detail(project_id)
    for run_detail in project.get("workflow_runs", []):
        run = run_detail.get("run", {})
        if run.get("type") == workflow_type:
            return run_detail
    return None


async def poll_until_status(
    project_id: str,
    workflow_type: str,
    target_statuses: set[str],
    timeout_s: float = DEFAULT_TIMEOUT_S,
    interval_s: float = DEFAULT_POLL_INTERVAL_S,
) -> dict[str, Any]:
    """Poll the project until a run of the given type reaches one of the target statuses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        detail = await find_workflow_run_by_type(project_id, workflow_type)
        if detail:
            status = detail.get("run", {}).get("status")
            if status in target_statuses:
                logger.info(
                    "Workflow %s reached status=%s",
                    workflow_type,
                    status,
                )
                return detail
        await asyncio.sleep(interval_s)
    raise TimeoutError(
        f"Workflow '{workflow_type}' did not reach any of {target_statuses} "
        f"within {timeout_s}s for project {project_id}"
    )


async def _fetch_project_detail(
    client: httpx.AsyncClient, project_id: str
) -> dict[str, Any]:
    resp = await client.get(
        f"/api/project/{project_id}", params={"include_internal": True}
    )
    resp.raise_for_status()
    return resp.json()


async def get_project_detail(project_id: str) -> dict[str, Any]:
    """Fetch full project details including workflow runs, issues, and files."""
    async with _build_client() as client:
        return await _fetch_project_detail(client, project_id)


async def get_workflow_state(workflow_run_id: str) -> dict[str, Any]:
    """Fetch the full state of a single workflow run."""
    async with _build_client() as client:
        resp = await client.get(f"/api/workflows/{workflow_run_id}")
        resp.raise_for_status()
        return resp.json()


async def start_workflow(config: dict[str, Any]) -> str:
    """Start a workflow via POST /api/workflows/start.

    Args:
        config: A WorkflowConfig dict (must include 'type' and 'project_id').

    Returns:
        The workflow_run_id of the newly created run.

    Note:
        This endpoint takes the `WorkflowConfig` union, which is untagged: a
        payload carrying only `type` and `project_id` validates against the
        first union member that accepts it, not the one matching `type`. Pass a
        config with fields unique to the target workflow, or use
        `start_workflow_types`, whose endpoint takes an explicit request model.
    """
    async with _build_client() as client:
        resp = await client.post("/api/workflows/start", json=config)
        resp.raise_for_status()
        body = resp.json()
        logger.info(
            "Started workflow type=%s, workflow_run_id=%s",
            config.get("type"),
            body.get("workflow_run_id"),
        )
        return body["workflow_run_id"]


async def create_revision(project_id: str) -> int:
    """Create a new revision on a project and return its number.

    Creating a revision archives the current revision's issues and cancels any
    workflow still running against it, so anything that must belong to the
    outgoing revision has to be uploaded before this is called. The new main
    document is uploaded afterwards, through TUS.
    """
    async with _build_client() as client:
        resp = await client.post(f"/api/project/{project_id}/revisions")
        resp.raise_for_status()
        revision = int(resp.json()["revision"])

    logger.info("Created revision %s on project %s", revision, project_id)
    return revision


async def start_workflow_types(project_id: str, workflow_types: list[str]) -> None:
    """Start workflows on an existing project.

    Goes through `/api/workflows/start-multiple`, whose request model names
    `workflow_types` explicitly, rather than `/api/workflows/start`, whose
    `WorkflowConfig` union is untagged and silently mis-resolves a minimal
    payload (a bare `{type, project_id}` validates as `HumanApprovalConfig`,
    and the run then fails constructing its state). This is also the endpoint
    the app itself uses to start analyses.

    Returns nothing even though the endpoint now reports `workflow_run_ids`:
    the caller tracks the run with `poll_until_complete`, which finds it on the
    project by type. That is what the other e2e suites do, and it keeps this
    helper usable for the multi-workflow case where the ids would need pairing
    back up with their types anyway.
    """
    payload: dict[str, Any] = {
        "project_id": project_id,
        "workflow_types": workflow_types,
    }
    openai_api_key = os.environ.get("EVAL_API_OPENAI_API_KEY")
    if openai_api_key:
        payload["openai_api_key"] = openai_api_key

    async with _build_client() as client:
        resp = await client.post("/api/workflows/start-multiple", json=payload)
        resp.raise_for_status()

    logger.info("Started %s on project %s", workflow_types, project_id)


async def poll_workflow_run_until_complete(
    workflow_run_id: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    interval_s: float = DEFAULT_POLL_INTERVAL_S,
) -> dict[str, Any]:
    """Poll a specific workflow run until it reaches 'completed' status.

    Args:
        workflow_run_id: The workflow run ID to poll.
        timeout_s: Max seconds to wait.
        interval_s: Seconds between polling attempts.

    Returns:
        The WorkflowRunDetail dict (with 'run' and 'state' keys).

    Raises:
        TimeoutError: If the workflow does not complete within timeout_s.
    """
    deadline = time.monotonic() + timeout_s

    async with _build_client() as client:
        while time.monotonic() < deadline:
            try:
                resp = await client.get(f"/api/workflows/{workflow_run_id}")
                resp.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError) as e:
                logger.warning(
                    "Polling workflow run %s failed (%s); retrying",
                    workflow_run_id,
                    type(e).__name__,
                )
                await asyncio.sleep(interval_s)
                continue
            run_detail = resp.json()
            status = run_detail.get("run", {}).get("status")
            if status == "completed":
                logger.info("Workflow run %s completed", workflow_run_id)
                check_workflow_errors(run_detail.get("state") or {})
                return run_detail
            if status in TERMINAL_FAILURE_STATUSES:
                # A run that has failed or been cancelled will never reach
                # "completed", so polling on would only burn the timeout and
                # report the wrong cause.
                check_workflow_errors(run_detail.get("state") or {})
                raise WorkflowCompletionError(
                    f"Workflow run '{workflow_run_id}' ended with status "
                    f"'{status}'. The run carried no error details; check the "
                    f"backend log for the traceback."
                )
            logger.debug(
                "Workflow run %s status=%s, polling again in %ss",
                workflow_run_id,
                status,
                interval_s,
            )
            await asyncio.sleep(interval_s)

    raise TimeoutError(
        f"Workflow run '{workflow_run_id}' did not complete within {timeout_s}s"
    )


async def poll_until_complete(
    project_id: str,
    workflow_type: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    interval_s: float = DEFAULT_POLL_INTERVAL_S,
) -> dict[str, Any]:
    """Poll the project endpoint until the target workflow is completed.

    Returns the WorkflowRunDetail dict for the completed workflow.
    Raises TimeoutError if the workflow does not complete within timeout_s.
    """
    deadline = time.monotonic() + timeout_s

    async with _build_client() as client:
        while time.monotonic() < deadline:
            try:
                project = await _fetch_project_detail(client, project_id)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                # The workflow is still running server-side; only this poll
                # failed. Losing the whole eval sample over it would report a
                # busy server as a workflow failure.
                logger.warning(
                    "Polling %s for project %s failed (%s); retrying",
                    workflow_type,
                    project_id,
                    type(e).__name__,
                )
                await asyncio.sleep(interval_s)
                continue
            for run_detail in project.get("workflow_runs", []):
                run = run_detail.get("run", {})
                if run.get("type") != workflow_type:
                    continue
                status = run.get("status")
                if status == "completed":
                    logger.info(
                        "Workflow %s completed (run_id=%s)",
                        workflow_type,
                        run.get("id"),
                    )
                    check_workflow_errors(run_detail.get("state") or {})
                    return run_detail
                if status in TERMINAL_FAILURE_STATUSES:
                    # A failed or cancelled run will never reach "completed",
                    # so polling on would only burn the timeout and report the
                    # wrong cause.
                    check_workflow_errors(run_detail.get("state") or {})
                    raise WorkflowCompletionError(
                        f"Workflow '{workflow_type}' ended with status "
                        f"'{status}' (run_id={run.get('id')}) for project "
                        f"{project_id}. The run carried no error details; "
                        f"check the backend log for the traceback."
                    )
                logger.debug(
                    "Workflow %s status=%s, polling again in %ss",
                    workflow_type,
                    status,
                    interval_s,
                )
            await asyncio.sleep(interval_s)

    raise TimeoutError(
        f"Workflow '{workflow_type}' did not complete within {timeout_s}s "
        f"for project {project_id}"
    )
