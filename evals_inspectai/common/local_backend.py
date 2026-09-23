"""Small local-backend lifecycle helper for API end-to-end Inspect evals.

The evaluation process owns this loopback server. It uses the developer's
configured database and credentials, which may point at remote services.
"""

import atexit
import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values


class LocalBackend:
    """Start one API server lazily and stop it when the Inspect process exits.

    Args:
        model: Inspect AI model name (e.g. ``"openai/gpt-5.6-terra"``) to pass
            to the backend as ``EVAL_WORKFLOW_MODEL``.  When omitted the active
            Inspect model is detected automatically from ``active_model()``.
        cwd: Working directory for the backend subprocess.  Use this when the
            backend you want to start lives in a subdirectory rather than the
            current working directory (e.g. ``Path(__file__).parents[3]`` for a
            ``draft-detective/`` eval that targets its own backend).
    """

    def __init__(
        self,
        model: str | None = None,
        cwd: Path | None = None,
    ) -> None:
        self._model = model
        self._cwd = cwd or Path(__file__).resolve().parents[2]
        self._lock = asyncio.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._url: str | None = None
        self._log_path: Path | None = None
        self._started_model: str | None = None
        atexit.register(self.shutdown)

    async def ensure_started(self) -> str:
        async with self._lock:
            model = self._model or _active_model_name()
            if self._url and self._process and self._process.poll() is None:
                if model != self._started_model:
                    raise ValueError("Create a new LocalBackend for each model")
                return self._url
            self.shutdown()
            try:
                env = os.environ.copy()
                await _ensure_local_database(env, self._cwd)
                # HTTP-only evals do not need MCP OAuth credentials.
                env["MCP_ENABLED"] = "false"
                if model:
                    env["EVAL_WORKFLOW_MODEL"] = model
                port = _free_port()
                self._url = f"http://127.0.0.1:{port}"
                self._started_model = model
                log_dir = self._cwd / "logs"
                log_dir.mkdir(exist_ok=True)
                self._log_path = log_dir / f"inspect-backend-{port}.log"
                with self._log_path.open("wb") as log_file:
                    self._process = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            "lib.api.main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                        ],
                        env=env,
                        cwd=self._cwd,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                    )
                await self._wait_for_health()
            except BaseException:
                # Includes cancellation, database failure, and spawn failure.
                self.shutdown()
                raise
            return self._url

    async def _wait_for_health(self) -> None:
        assert self._url is not None
        deadline = time.monotonic() + 30
        async with httpx.AsyncClient(timeout=1.0) as client:
            while time.monotonic() < deadline:
                if self._process and self._process.poll() is not None:
                    raise RuntimeError(self._failure_message())
                try:
                    response = await client.get(f"{self._url}/api/health")
                    if response.is_success:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.25)
        raise RuntimeError(self._failure_message("Timed out waiting for local backend"))

    def _failure_message(
        self, prefix: str = "Local backend exited during startup"
    ) -> str:
        detail = ""
        if self._log_path and self._log_path.exists():
            detail = self._log_path.read_text(errors="replace")[-4000:]
        return f"{prefix}. Backend log: {self._log_path}\n{detail}"

    def shutdown(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._process = None
        self._url = None
        self._started_model = None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _ensure_local_database(env: dict[str, str], cwd: Path) -> None:
    """Start the repository's Compose database only when a local DB is configured."""
    database_url = env.get("DATABASE_URL") or dotenv_values(cwd / ".env").get(
        "DATABASE_URL"
    )
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured before starting evals")

    parsed = urlparse(str(database_url))
    host = parsed.hostname or ""
    port = parsed.port or 5432
    if host in {"0.0.0.0", "127.0.0.1", "localhost"}:
        check_host = "127.0.0.1" if host == "0.0.0.0" else host
        if not await asyncio.to_thread(_port_open, check_host, port):
            result = await asyncio.to_thread(
                subprocess.run,
                ["docker", "compose", "up", "-d", "db"],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=30,
            )
            if result.returncode:
                output = "\n".join(
                    part
                    for part in (result.stdout.strip(), result.stderr.strip())
                    if part
                )
                raise RuntimeError(
                    "Could not start the local Compose database (service: db). "
                    f"Docker reported:\n{output or f'exit status {result.returncode}'}"
                )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if await asyncio.to_thread(_port_open, check_host, port):
                    return
                await asyncio.sleep(0.25)
            raise RuntimeError("Timed out waiting for local Postgres to start")
        return

    # Do not try to start remote infrastructure. Workflows still write eval data.
    if not await asyncio.to_thread(_port_open, host, port):
        raise RuntimeError(
            f"Configured database {host}:{port} is unavailable; refusing to start "
            "a local Docker database for a non-local DATABASE_URL."
        )


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _active_model_name() -> str | None:
    """Return the Inspect AI model name currently under evaluation, or None."""
    from inspect_ai.model._model import active_model

    model = active_model()
    return str(model) if model is not None else None
