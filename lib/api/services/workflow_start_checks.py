"""Checks every workflow start makes before it creates a run."""

from fastapi import HTTPException

from lib.config.env import config as env_config
from lib.config.llm_models import LLMModel
from lib.models.project import AccessLevel, Project
from lib.models.user import User
from lib.services.files.service import assert_project_has_main_file
from lib.services.projects.service import get_project_access
from lib.services.users import get_user_decrypted_api_key


def assert_api_key_available(
    user: User, request_key: str | None, requires_key: bool
) -> None:
    """Raise HTTP 422 when a workflow needs an API key but none is configured."""
    if not requires_key:
        return
    has_api_key = bool(
        request_key or get_user_decrypted_api_key(user) or env_config.OPENAI_API_KEY
    )
    if not has_api_key:
        raise HTTPException(
            status_code=422,
            detail="No OpenAI API key configured. Please add your API key in account settings.",
        )


def assert_model_override_allowed(model: str | None) -> None:
    """Raise HTTP 422 when a request names a model the server will not run.

    The name must carry its provider: agents choose their API key, reasoning
    settings and web-search tool by it, so a bare name would run without them.
    """
    if model is None:
        return
    if not env_config.ALLOW_WORKFLOW_MODEL_OVERRIDE:
        raise HTTPException(
            status_code=422,
            detail="This server does not accept a workflow model override (ALLOW_WORKFLOW_MODEL_OVERRIDE is off).",
        )
    override = LLMModel.from_model_name(model)
    if not override.provider or not override.name:
        raise HTTPException(
            status_code=422,
            detail=f"Model {model!r} must name its provider, e.g. 'openai:gpt-5.6-sol'.",
        )


async def authorized_project(
    project_id: str, user: User, *, model: str | None
) -> Project:
    """The project, once the user may start workflows on it.

    Raises:
        HTTPException: 404 if the project doesn't exist, 403 without write
            access, 422 if it has no main file or the model override is not
            allowed
    """
    project, _ = await get_project_access(
        project_id, user=user, required_level=AccessLevel.WRITE
    )
    assert_model_override_allowed(model)
    await assert_project_has_main_file(project_id, project.current_revision)
    return project
