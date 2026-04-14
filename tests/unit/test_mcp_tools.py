"""Unit tests for MCP tool functions with mocked service dependencies."""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Patch auth factory before importing the MCP module (see test_mcp_server.py).
import lib.api.mcp_auth as _mcp_auth_mod

_orig = _mcp_auth_mod.create_mcp_auth
_mcp_auth_mod.create_mcp_auth = lambda: None

from lib.api.mcp import (  # noqa: E402
    _build_project_url,
    _build_settings_url,
    _build_tus_url,
    _require_api_key,
    _resolve_user,
    create_project,
    create_revision,
    export_project_docx,
    get_project,
    get_tus_upload_credentials,
    list_project_files,
    list_projects,
    list_revisions,
    remove_reference_file,
    run_workflow,
)

_mcp_auth_mod.create_mcp_auth = _orig


def _make_token(email: str = "alice@example.com", name: str = "Alice") -> MagicMock:
    token = MagicMock()
    token.claims = {"email": email, "name": name}
    return token


def _make_user(email: str = "alice@example.com", name: str = "Alice") -> MagicMock:
    user = MagicMock()
    user.email = email
    user.name = name
    user.id = uuid4()
    return user


# --- _build_project_url ---


def test_build_project_url():
    url = _build_project_url("abc-123")
    assert url.endswith("/projects/abc-123")
    assert not url.endswith("//projects/abc-123")


def test_build_project_url_strips_trailing_slash():
    with patch("lib.api.mcp.env_config") as mock_cfg:
        mock_cfg.FRONTEND_URL = "https://app.example.com/"
        result = _build_project_url("proj-1")
    assert result == "https://app.example.com/projects/proj-1"


# --- _build_settings_url ---


def test_build_settings_url():
    url = _build_settings_url()
    assert url.endswith("/account")
    assert not url.endswith("//account")


def test_build_settings_url_strips_trailing_slash():
    with patch("lib.api.mcp.env_config") as mock_cfg:
        mock_cfg.FRONTEND_URL = "https://app.example.com/"
        result = _build_settings_url()
    assert result == "https://app.example.com/account"


# --- _require_api_key ---


def test_require_api_key_passes_when_user_has_encrypted_key():
    user = _make_user()
    user.encrypted_openai_api_key = "some-encrypted-value"
    with patch("lib.api.mcp.env_config") as mock_cfg:
        mock_cfg.OPENAI_API_KEY = None
        _require_api_key(user)  # should not raise


def test_require_api_key_passes_when_env_has_key():
    user = _make_user()
    user.encrypted_openai_api_key = None
    with patch("lib.api.mcp.env_config") as mock_cfg:
        mock_cfg.OPENAI_API_KEY = "sk-env-key"
        _require_api_key(user)  # should not raise


def test_require_api_key_raises_when_no_key_anywhere():
    user = _make_user()
    user.encrypted_openai_api_key = None
    with patch("lib.api.mcp.env_config") as mock_cfg:
        mock_cfg.OPENAI_API_KEY = None
        mock_cfg.FRONTEND_URL = "https://app.example.com"
        with pytest.raises(ValueError, match="Settings page"):
            _require_api_key(user)


def test_require_api_key_error_message_contains_email():
    user = _make_user(email="carol@example.com")
    user.encrypted_openai_api_key = None
    with patch("lib.api.mcp.env_config") as mock_cfg:
        mock_cfg.OPENAI_API_KEY = None
        mock_cfg.FRONTEND_URL = "https://app.example.com"
        with pytest.raises(ValueError, match="carol@example.com"):
            _require_api_key(user)


# --- _resolve_user ---


@pytest.mark.asyncio
async def test_resolve_user_calls_get_or_create():
    mock_user = _make_user()
    token = _make_token()

    with patch(
        "lib.api.mcp.get_or_create_user_by_email",
        new=AsyncMock(return_value=mock_user),
    ) as mock_get:
        result = await _resolve_user(token)

    mock_get.assert_awaited_once_with(email="alice@example.com", name="Alice")
    assert result is mock_user


@pytest.mark.asyncio
async def test_resolve_user_raises_when_email_missing():
    token = MagicMock()
    token.claims = {"name": "No Email"}

    with pytest.raises(RuntimeError, match="Token missing 'email' claim"):
        await _resolve_user(token)


@pytest.mark.asyncio
async def test_resolve_user_falls_back_email_as_name():
    token = MagicMock()
    token.claims = {"email": "bob@example.com"}
    mock_user = _make_user(email="bob@example.com", name="bob@example.com")

    with patch(
        "lib.api.mcp.get_or_create_user_by_email",
        new=AsyncMock(return_value=mock_user),
    ) as mock_get:
        await _resolve_user(token)

    mock_get.assert_awaited_once_with(email="bob@example.com", name="bob@example.com")


@pytest.mark.asyncio
async def test_resolve_user_azure_preferred_username_top_level():
    """Azure v2.0 tokens expose preferred_username at the top level."""
    token = MagicMock()
    token.claims = {"preferred_username": "jane@example.com", "name": "Jane Doe"}
    mock_user = _make_user(email="jane@example.com", name="Jane Doe")

    with patch(
        "lib.api.mcp.get_or_create_user_by_email",
        new=AsyncMock(return_value=mock_user),
    ) as mock_get:
        result = await _resolve_user(token)

    mock_get.assert_awaited_once_with(email="jane@example.com", name="Jane Doe")
    assert result is mock_user


@pytest.mark.asyncio
async def test_resolve_user_azure_preferred_username_no_name():
    """Falls back to preferred_username as the display name."""
    token = MagicMock()
    token.claims = {"preferred_username": "jane@example.com"}
    mock_user = _make_user(email="jane@example.com", name="jane@example.com")

    with patch(
        "lib.api.mcp.get_or_create_user_by_email",
        new=AsyncMock(return_value=mock_user),
    ) as mock_get:
        result = await _resolve_user(token)

    mock_get.assert_awaited_once_with(email="jane@example.com", name="jane@example.com")
    assert result is mock_user


@pytest.mark.asyncio
async def test_resolve_user_azure_upstream_claims_email():
    """FastMCP reference JWT embeds Azure claims under upstream_claims."""
    token = MagicMock()
    token.claims = {"upstream_claims": {"email": "jane@example.com", "name": "Jane Doe"}}
    mock_user = _make_user(email="jane@example.com", name="Jane Doe")

    with patch(
        "lib.api.mcp.get_or_create_user_by_email",
        new=AsyncMock(return_value=mock_user),
    ) as mock_get:
        result = await _resolve_user(token)

    mock_get.assert_awaited_once_with(email="jane@example.com", name="Jane Doe")
    assert result is mock_user


@pytest.mark.asyncio
async def test_resolve_user_azure_upstream_claims_preferred_username():
    """Falls back to upstream_claims.preferred_username when no email."""
    token = MagicMock()
    token.claims = {"upstream_claims": {"preferred_username": "jane@example.com"}}
    mock_user = _make_user(email="jane@example.com", name="jane@example.com")

    with patch(
        "lib.api.mcp.get_or_create_user_by_email",
        new=AsyncMock(return_value=mock_user),
    ) as mock_get:
        result = await _resolve_user(token)

    mock_get.assert_awaited_once_with(email="jane@example.com", name="jane@example.com")
    assert result is mock_user


@pytest.mark.asyncio
async def test_resolve_user_email_takes_priority_over_preferred_username():
    """Top-level email wins over preferred_username."""
    token = MagicMock()
    token.claims = {
        "email": "official@example.com",
        "preferred_username": "alias@example.com",
        "name": "Jane Doe",
    }
    mock_user = _make_user(email="official@example.com", name="Jane Doe")

    with patch(
        "lib.api.mcp.get_or_create_user_by_email",
        new=AsyncMock(return_value=mock_user),
    ) as mock_get:
        result = await _resolve_user(token)

    mock_get.assert_awaited_once_with(email="official@example.com", name="Jane Doe")
    assert result is mock_user


@pytest.mark.asyncio
async def test_resolve_user_raises_when_no_email_anywhere():
    token = MagicMock()
    token.claims = {"name": "No Email User", "upstream_claims": {"name": "No Email"}}

    with pytest.raises(RuntimeError, match="Token missing 'email' claim"):
        await _resolve_user(token)


@pytest.mark.asyncio
async def test_resolve_user_raises_when_preferred_username_not_email():
    token = MagicMock()
    token.claims = {"preferred_username": "jdoe"}

    with pytest.raises(RuntimeError, match="not a valid email address"):
        await _resolve_user(token)


# --- create_project ---


@pytest.mark.asyncio
async def test_create_project_returns_ids_and_url():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    file_record = MagicMock()
    file_record.id = uuid4()
    ctx = AsyncMock()

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch(
            "lib.api.mcp.create_project_record",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "lib.api.mcp.finalize_file",
            new=AsyncMock(return_value=file_record),
        ),
    ):
        raw = await create_project(
            title="Test", content_markdown="# Hello", ctx=ctx, token=_make_token()
        )

    data = json.loads(raw)
    assert data["project_id"] == str(project.id)
    assert data["file_id"] == str(file_record.id)
    assert "/projects/" in data["project_url"]


@pytest.mark.asyncio
async def test_create_project_returns_project_url():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.create_project_record", new=AsyncMock(return_value=project)),
        patch("lib.api.mcp.finalize_file", new=AsyncMock(return_value=MagicMock(id=uuid4()))),
    ):
        result = await create_project(
            title="T", content_markdown="md", ctx=AsyncMock(), token=_make_token()
        )

    data = json.loads(result)
    assert str(project.id) in data["project_url"]


# --- run_workflow ---


@pytest.mark.asyncio
async def test_run_workflow_rejects_invalid_type():
    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=_make_user())),
    ):
        with pytest.raises(ValueError, match="Unknown workflow_type 'nonexistent'"):
            await run_workflow(
                project_id="p1",
                workflow_types=["nonexistent"],
                token=_make_token(),
            )


@pytest.mark.asyncio
async def test_run_workflow_delegates_to_blocking_runner():
    user = _make_user()
    project_json = json.dumps({"id": "p1", "project_url": "http://x/projects/p1"})

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch(
            "lib.api.mcp.run_multiple_workflows_blocking", new=AsyncMock()
        ) as mock_run,
        patch(
            "lib.api.mcp._get_project_details_json",
            new=AsyncMock(return_value=project_json),
        ),
    ):
        result = await run_workflow(
            project_id="p1",
            workflow_types=["document_processing"],
            token=_make_token(),
        )

    mock_run.assert_awaited_once()
    assert json.loads(result)["id"] == "p1"


@pytest.mark.asyncio
async def test_run_workflow_raises_when_no_api_key():
    user = _make_user()
    user.encrypted_openai_api_key = None

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.env_config") as mock_cfg,
    ):
        mock_cfg.OPENAI_API_KEY = None
        mock_cfg.FRONTEND_URL = "https://app.example.com"
        with pytest.raises(ValueError, match="Settings page"):
            await run_workflow(
                project_id="p1",
                workflow_types=["document_processing"],
                token=_make_token(),
            )


# --- list_projects ---


@pytest.mark.asyncio
async def test_list_projects_returns_project_list():
    user = _make_user()
    project_item = MagicMock()
    project_item.project.id = uuid4()
    project_item.project.title = "My Project"

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch(
            "lib.api.mcp.get_user_projects",
            new=AsyncMock(return_value=[project_item]),
        ),
    ):
        raw = await list_projects(token=_make_token())

    data = json.loads(raw)
    assert len(data) == 1
    assert data[0]["title"] == "My Project"
    assert data[0]["project_id"] == str(project_item.project.id)
    assert "/projects/" in data[0]["project_url"]


@pytest.mark.asyncio
async def test_list_projects_returns_empty_list_when_no_projects():
    user = _make_user()

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_user_projects", new=AsyncMock(return_value=[])),
    ):
        raw = await list_projects(token=_make_token())

    assert json.loads(raw) == []


def _make_aiofiles_open_mock(read_data: bytes) -> MagicMock:
    """Return a mock for aiofiles.open that yields a file-like object returning read_data."""
    mock_file = AsyncMock()
    mock_file.read.return_value = read_data
    mock_open = MagicMock()
    mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
    mock_open.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_open


# --- export_project_docx ---


@pytest.mark.asyncio
async def test_export_project_docx_returns_file():
    from fastmcp.utilities.types import File

    user = _make_user()
    project_id = str(uuid4())
    fake_docx = b"PK\x03\x04fake-docx-bytes"

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(MagicMock(), MagicMock()))),
        patch(
            "lib.api.mcp.get_or_generate_docx",
            new=AsyncMock(return_value=("/tmp/report.docx", "report_comments.docx")),
        ),
        patch("lib.api.mcp.aiofiles.open", _make_aiofiles_open_mock(fake_docx)),
    ):
        result = await export_project_docx(project_id=project_id, token=_make_token())

    assert isinstance(result, File)
    assert result._name == "report_comments.docx"
    assert result.data == fake_docx


@pytest.mark.asyncio
async def test_export_project_docx_passes_filters_to_service():
    from lib.workflows.models import SeverityEnum, WorkflowRunType

    user = _make_user()
    project_id = str(uuid4())

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(MagicMock(), MagicMock()))),
        patch(
            "lib.api.mcp.get_or_generate_docx",
            new=AsyncMock(return_value=("/tmp/out.docx", "out_comments.docx")),
        ) as mock_gen,
        patch("lib.api.mcp.aiofiles.open", _make_aiofiles_open_mock(b"")),
    ):
        await export_project_docx(
            project_id=project_id,
            workflow_types=[WorkflowRunType.CLAIM_EXTRACTION],
            severities=[SeverityEnum.HIGH],
            token=_make_token(),
        )

    _, kwargs = mock_gen.call_args
    assert kwargs["workflow_types"] == [WorkflowRunType.CLAIM_EXTRACTION]
    assert kwargs["severities"] == [SeverityEnum.HIGH]


# --- get_project ---


@pytest.mark.asyncio
async def test_get_project_returns_details():
    user = _make_user()
    expected = json.dumps({"id": "p1", "title": "Test"})

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch(
            "lib.api.mcp._get_project_details_json",
            new=AsyncMock(return_value=expected),
        ) as mock_details,
    ):
        result = await get_project(project_id="p1", token=_make_token())

    from lib.models.project import AccessLevel

    mock_details.assert_awaited_once_with("p1", AccessLevel.READ, user, revision=None)
    assert json.loads(result)["title"] == "Test"


# --- list_project_files ---


@pytest.mark.asyncio
async def test_list_project_files_returns_files_with_reference():
    from lib.workflows.reference_file_matching.state import MatchSource, ReferenceFileMatch

    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    project_id = str(project.id)

    file1 = MagicMock()
    file1.id = uuid4()
    file1.file_name = "paper.pdf"
    file1.file_size = 12345
    file1.file_type = "application/pdf"
    file1.role = "support"
    file1.revision = None

    project.current_revision = 1

    ref_id = str(uuid4())
    match = ReferenceFileMatch(reference_id=ref_id, file_id=str(file1.id), source=MatchSource.MANUAL_UPLOAD)

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(project, MagicMock()))),
        patch("lib.api.mcp.get_project_files_list_items", new=AsyncMock(return_value=[file1])),
        patch("lib.api.mcp.get_file_reference_matches", new=AsyncMock(return_value=[match])),
    ):
        raw = await list_project_files(project_id=project_id, token=_make_token())

    data = json.loads(raw)
    assert len(data) == 1
    assert data[0]["file_id"] == str(file1.id)
    assert data[0]["file_name"] == "paper.pdf"
    assert data[0]["file_size"] == 12345
    assert data[0]["file_type"] == "application/pdf"
    assert data[0]["role"] == "support"
    assert data[0]["reference_id"] == ref_id


@pytest.mark.asyncio
async def test_list_project_files_null_reference_when_unmatched():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    project.current_revision = 1

    file1 = MagicMock()
    file1.id = uuid4()
    file1.file_name = "extra.pdf"
    file1.file_size = 500
    file1.file_type = "application/pdf"
    file1.role = "support"
    file1.revision = None

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(project, MagicMock()))),
        patch("lib.api.mcp.get_project_files_list_items", new=AsyncMock(return_value=[file1])),
        patch("lib.api.mcp.get_file_reference_matches", new=AsyncMock(return_value=[])),
    ):
        raw = await list_project_files(project_id=str(project.id), token=_make_token())

    data = json.loads(raw)
    assert data[0]["reference_id"] is None


@pytest.mark.asyncio
async def test_list_project_files_returns_empty_list():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    project.current_revision = 1

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(project, MagicMock()))),
        patch("lib.api.mcp.get_project_files_list_items", new=AsyncMock(return_value=[])),
        patch("lib.api.mcp.get_file_reference_matches", new=AsyncMock(return_value=[])),
    ):
        raw = await list_project_files(project_id=str(project.id), token=_make_token())

    assert json.loads(raw) == []


# --- remove_reference_file ---


@pytest.mark.asyncio
async def test_remove_reference_file_returns_file_and_unlinked_refs():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    file_id = str(uuid4())
    ref_id = str(uuid4())

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(project, MagicMock()))),
        patch("lib.api.mcp.delete_project_files", new=AsyncMock(return_value=1)),
        patch("lib.api.mcp.remove_file_from_references", new=AsyncMock(return_value=[ref_id])),
    ):
        raw = await remove_reference_file(
            project_id=str(project.id), file_id=file_id, token=_make_token()
        )

    data = json.loads(raw)
    assert data["file_id"] == file_id
    assert data["removed_from_reference_ids"] == [ref_id]


@pytest.mark.asyncio
async def test_remove_reference_file_raises_when_not_found():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    file_id = str(uuid4())

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(project, MagicMock()))),
        patch("lib.api.mcp.delete_project_files", new=AsyncMock(return_value=0)),
    ):
        with pytest.raises(ValueError, match="not found in project"):
            await remove_reference_file(
                project_id=str(project.id), file_id=file_id, token=_make_token()
            )


@pytest.mark.asyncio
async def test_remove_reference_file_with_no_associations():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    file_id = str(uuid4())

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(project, MagicMock()))),
        patch("lib.api.mcp.delete_project_files", new=AsyncMock(return_value=1)),
        patch("lib.api.mcp.remove_file_from_references", new=AsyncMock(return_value=[])),
    ):
        raw = await remove_reference_file(
            project_id=str(project.id), file_id=file_id, token=_make_token()
        )

    data = json.loads(raw)
    assert data["removed_from_reference_ids"] == []


# --- _build_tus_url ---


def test_build_tus_url_strips_mcp_suffix():
    with patch("lib.api.mcp.env_config") as mock_cfg:
        mock_cfg.MCP_BASE_URL = "https://app.example.com/mcp"
        result = _build_tus_url()
    assert result == "https://app.example.com/tus"


def test_build_tus_url_handles_trailing_slash_after_stripping():
    with patch("lib.api.mcp.env_config") as mock_cfg:
        mock_cfg.MCP_BASE_URL = "https://app.example.com/mcp"
        result = _build_tus_url()
    assert not result.endswith("//tus")
    assert result.endswith("/tus")


# --- get_tus_upload_credentials ---


@pytest.mark.asyncio
async def test_get_tus_upload_credentials_returns_required_fields():
    import jwt as pyjwt

    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    project_id = str(uuid4())

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(project, MagicMock()))),
        patch("lib.api.mcp.env_config") as mock_cfg,
    ):
        mock_cfg.MCP_BASE_URL = "https://app.example.com/mcp"
        mock_cfg.AUTH_SECRET = "test-secret"
        raw = await get_tus_upload_credentials(project_id=project_id, token=_make_token())

    data = json.loads(raw)
    assert data["tus_url"] == "https://app.example.com/tus"
    assert "bearer_token" in data
    assert data["expires_in_seconds"] == 900
    assert data["required_metadata"]["project_id"] == project_id
    assert data["required_metadata"]["role"] == "support"
    assert data["required_metadata"]["reference_id"] is None
    assert "instructions" in data

    decoded = pyjwt.decode(
        data["bearer_token"],
        "test-secret",
        algorithms=["HS512"],
        issuer="ai-reviewer",
        audience="ai-reviewer-api",
    )
    assert decoded["email"] == user.email
    assert decoded["name"] == user.name


@pytest.mark.asyncio
async def test_get_tus_upload_credentials_includes_reference_id():
    user = _make_user()
    project = MagicMock()
    ref_id = str(uuid4())

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(project, MagicMock()))),
        patch("lib.api.mcp.env_config") as mock_cfg,
    ):
        mock_cfg.MCP_BASE_URL = "https://app.example.com/mcp"
        mock_cfg.AUTH_SECRET = "test-secret"
        raw = await get_tus_upload_credentials(
            project_id=str(uuid4()), reference_id=ref_id, token=_make_token()
        )

    data = json.loads(raw)
    assert data["required_metadata"]["reference_id"] == ref_id


@pytest.mark.asyncio
async def test_get_tus_upload_credentials_bearer_token_expires_in_one_hour():
    from datetime import datetime, timezone

    import jwt as pyjwt

    user = _make_user()

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(MagicMock(), MagicMock()))),
        patch("lib.api.mcp.env_config") as mock_cfg,
    ):
        mock_cfg.MCP_BASE_URL = "https://app.example.com/mcp"
        mock_cfg.AUTH_SECRET = "test-secret"
        before = datetime.now(timezone.utc)
        raw = await get_tus_upload_credentials(project_id=str(uuid4()), token=_make_token())
        after = datetime.now(timezone.utc)

    data = json.loads(raw)
    decoded = pyjwt.decode(
        data["bearer_token"],
        "test-secret",
        algorithms=["HS512"],
        issuer="ai-reviewer",
        audience="ai-reviewer-api",
    )
    exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    iat = datetime.fromtimestamp(decoded["iat"], tz=timezone.utc)

    assert exp - iat >= timedelta(minutes=14)
    assert exp - iat <= timedelta(minutes=15, seconds=5)


# --- create_project without content_markdown (TUS path) ---


@pytest.mark.asyncio
async def test_create_project_without_content_returns_next_step():
    """When content_markdown is omitted, no file is created and next_step is returned."""
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.create_project_record", new=AsyncMock(return_value=project)),
        patch("lib.api.mcp.finalize_file", new=AsyncMock()) as mock_finalize,
    ):
        raw = await create_project(title="Test", ctx=AsyncMock(), token=_make_token())

    data = json.loads(raw)
    assert data["project_id"] == str(project.id)
    assert "file_id" not in data
    assert "next_step" in data
    mock_finalize.assert_not_awaited()


# --- create_revision ---


@pytest.mark.asyncio
async def test_create_revision_with_content_returns_file_id():
    """When content_markdown is provided, the file is created inline."""
    user = _make_user()
    file_record = MagicMock()
    file_record.id = uuid4()

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.create_new_revision", new=AsyncMock(return_value=(2, ["claim_extraction"]))),
        patch("lib.api.mcp.finalize_file", new=AsyncMock(return_value=file_record)),
    ):
        raw = await create_revision(
            project_id=str(uuid4()),
            content_markdown="# Updated doc",
            token=_make_token(),
        )

    data = json.loads(raw)
    assert data["revision"] == 2
    assert data["file_id"] == str(file_record.id)
    assert data["previous_workflow_types"] == ["claim_extraction"]


@pytest.mark.asyncio
async def test_create_revision_without_content_returns_next_step():
    """When content_markdown is omitted, no file is created and next_step is returned."""
    user = _make_user()

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.create_new_revision", new=AsyncMock(return_value=(3, []))),
        patch("lib.api.mcp.finalize_file", new=AsyncMock()) as mock_finalize,
    ):
        raw = await create_revision(
            project_id=str(uuid4()),
            token=_make_token(),
        )

    data = json.loads(raw)
    assert data["revision"] == 3
    assert "file_id" not in data
    assert "next_step" in data
    mock_finalize.assert_not_awaited()


# --- list_revisions ---


@pytest.mark.asyncio
async def test_list_revisions_returns_all_revisions():
    user = _make_user()
    project = MagicMock()
    project.id = uuid4()
    project.current_revision = 2

    file_rev1 = MagicMock()
    file_rev1.id = uuid4()
    file_rev1.file_name = "v1.pdf"
    file_rev1.revision = 1
    file_rev1.created_at = MagicMock(isoformat=MagicMock(return_value="2026-01-01T00:00:00"))

    file_rev2 = MagicMock()
    file_rev2.id = uuid4()
    file_rev2.file_name = "v2.pdf"
    file_rev2.revision = 2
    file_rev2.created_at = MagicMock(isoformat=MagicMock(return_value="2026-04-10T00:00:00"))

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch("lib.api.mcp.get_project_access", new=AsyncMock(return_value=(project, MagicMock()))),
        patch("lib.api.mcp.get_files_by_project_id", new=AsyncMock(return_value=[file_rev1, file_rev2])),
    ):
        raw = await list_revisions(project_id=str(project.id), token=_make_token())

    data = json.loads(raw)
    assert len(data) == 2
    assert data[0]["revision"] == 1
    assert data[0]["is_current"] is False
    assert data[0]["main_file_name"] == "v1.pdf"
    assert data[1]["revision"] == 2
    assert data[1]["is_current"] is True
    assert data[1]["main_file_name"] == "v2.pdf"


# --- get_project with revision ---


@pytest.mark.asyncio
async def test_get_project_with_revision_passes_revision():
    user = _make_user()
    expected = json.dumps({"id": "p1", "title": "Test", "revision": 1})

    with (
        patch("lib.api.mcp._resolve_user", new=AsyncMock(return_value=user)),
        patch(
            "lib.api.mcp._get_project_details_json",
            new=AsyncMock(return_value=expected),
        ) as mock_details,
    ):
        await get_project(project_id="p1", revision=1, token=_make_token())

    from lib.models.project import AccessLevel

    mock_details.assert_awaited_once_with("p1", AccessLevel.READ, user, revision=1)
