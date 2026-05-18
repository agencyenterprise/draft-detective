"""Async HTTP client for calling the Draft Detective API in e2e evals."""

import asyncio
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt

from evals_inspectai.common.errors import check_workflow_errors

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_USER_EMAIL = "eval@draft-detective.local"
DEFAULT_USER_NAME = "E2E Eval Runner"
DEFAULT_POLL_INTERVAL_S = 5
DEFAULT_TIMEOUT_S = 300

JWT_ALGORITHM = "HS512"
JWT_ISSUER = "ai-reviewer"
JWT_AUDIENCE = "ai-reviewer-api"


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
        timeout=120.0,
    )


async def upload_and_start_analysis(
    file_content: str,
    workflow_types: list[str],
    file_name: str = "document.md",
    supporting_files: list[tuple[str, str]] | None = None,
) -> str:
    """Upload a document and start analysis workflows.

    Args:
        file_content: Markdown content of the main document.
        workflow_types: Workflow types to trigger (dependencies are auto-resolved
            server-side; pass only the leaf workflow).
        file_name: Display name for the main document.
        supporting_files: Optional list of (file_name, markdown_content) tuples
            uploaded alongside the main document as multipart `supporting_documents`.

    Returns the project_id.
    """
    async with _build_client() as client:
        tmp_paths: list[str] = []
        open_handles: list[Any] = []
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".md", mode="w", delete=False
            ) as tmp:
                tmp.write(file_content)
                main_path = tmp.name
            tmp_paths.append(main_path)

            multipart: list[tuple[str, tuple[str, Any, str]]] = []
            main_handle = open(main_path, "rb")
            open_handles.append(main_handle)
            multipart.append(
                ("main_document", (file_name, main_handle, "text/markdown"))
            )

            for sf_name, sf_content in supporting_files or []:
                with tempfile.NamedTemporaryFile(
                    suffix=".md", mode="w", delete=False
                ) as tmp_sf:
                    tmp_sf.write(sf_content)
                    sf_path = tmp_sf.name
                tmp_paths.append(sf_path)
                handle = open(sf_path, "rb")
                open_handles.append(handle)
                multipart.append(
                    ("supporting_documents", (sf_name, handle, "text/markdown"))
                )

            data: dict[str, Any] = {}
            for wt in workflow_types:
                data.setdefault("workflow_types", []).append(wt)

            openai_api_key = os.environ.get("EVAL_API_OPENAI_API_KEY")
            if openai_api_key:
                data["openai_api_key"] = openai_api_key

            resp = await client.post(
                "/api/start-analysis", files=multipart, data=data
            )
        finally:
            for h in open_handles:
                h.close()
            for p in tmp_paths:
                try:
                    os.unlink(p)
                except OSError:
                    pass

        resp.raise_for_status()
        body = resp.json()
        logger.info("Started analysis, project_id=%s", body["project_id"])
        return body["project_id"]


async def approve_workflow_run(workflow_run_id: str) -> None:
    """Trigger the human-approval gate for a workflow run."""
    async with _build_client() as client:
        resp = await client.post(
            f"/api/workflow-runs/{workflow_run_id}/approve"
        )
        resp.raise_for_status()
        logger.info("Approved workflow_run_id=%s", workflow_run_id)


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
            resp = await client.get(f"/api/workflows/{workflow_run_id}")
            resp.raise_for_status()
            run_detail = resp.json()
            status = run_detail.get("run", {}).get("status")
            if status == "completed":
                logger.info("Workflow run %s completed", workflow_run_id)
                check_workflow_errors(run_detail.get("state") or {})
                return run_detail
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
            project = await _fetch_project_detail(client, project_id)
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
