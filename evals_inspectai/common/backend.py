"""Eval-time backend selection, without changing process-wide API routing."""

from typing import TYPE_CHECKING

from evals_inspectai.common.api_client import _get_base_url

if TYPE_CHECKING:
    from evals_inspectai.common.local_backend import LocalBackend


def local_backend_for(
    backend: str = "remote", api_base_url: str | None = None
) -> "LocalBackend | None":
    """Use an existing server by default; starting repository code is opt-in.

    ``remote`` also covers an already-running localhost server. Authentication
    continues to use EVAL_API_AUTH_TOKEN or AUTH_SECRET in either mode.
    """
    if backend not in {"remote", "local"}:
        raise ValueError("backend must be 'remote' or 'local'")
    if backend == "remote":
        return None
    if api_base_url is not None:
        raise ValueError("api_base_url cannot be combined with backend='local'")

    # Remote evals must not need the application's local startup dependencies.
    from evals_inspectai.common.local_backend import LocalBackend

    return LocalBackend()


async def resolve_base_url(
    local_backend: "LocalBackend | None", api_base_url: str | None
) -> str:
    """Bind one solver invocation to one endpoint, including all nested calls."""
    if local_backend is not None:
        if api_base_url is not None:
            raise ValueError("api_base_url cannot be combined with a local backend")
        return await local_backend.ensure_started()
    return api_base_url or _get_base_url()
