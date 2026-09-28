"""Validate environment settings and pool wiring without opening connections."""

import runpy
from pathlib import Path

import pytest
from pydantic import ValidationError

from lib.config import env

ROOT = Path(__file__).resolve().parents[2]


def test_pool_environment_settings_reach_both_clients(monkeypatch):
    settings = {
        "DATABASE_POOL_SIZE": "12",
        "DATABASE_MAX_OVERFLOW": "6",
        "DATABASE_POOL_TIMEOUT": "45",
        "CHECKPOINTER_POOL_MIN_SIZE": "1",
        "CHECKPOINTER_POOL_MAX_SIZE": "7",
        "CHECKPOINTER_POOL_TIMEOUT": "50",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    configured = runpy.run_path(str(ROOT / "lib/config/env.py"))["config"]
    monkeypatch.setattr(env, "config", configured)
    engine = runpy.run_path(str(ROOT / "lib/config/database.py"))["async_engine"]
    pool = runpy.run_path(str(ROOT / "lib/agents/checkpointer.py"))["checkpointer_pool"]
    assert engine.pool.size() == 12
    assert engine.pool._max_overflow == 6
    assert engine.pool.timeout() == 45
    assert pool.min_size == 1
    assert pool.max_size == 7
    assert pool.timeout == 50


@pytest.mark.parametrize("settings", [
    {"DATABASE_POOL_SIZE": 0},
    {"DATABASE_MAX_OVERFLOW": -1},
    {"DATABASE_POOL_TIMEOUT": 0},
    {"CHECKPOINTER_POOL_MIN_SIZE": -1},
    {"CHECKPOINTER_POOL_MAX_SIZE": 0},
    {"CHECKPOINTER_POOL_TIMEOUT": 0},
    {"CHECKPOINTER_POOL_MIN_SIZE": 5, "CHECKPOINTER_POOL_MAX_SIZE": 4},
])
def test_invalid_pool_settings_fail_at_startup(settings):
    with pytest.raises(ValidationError):
        env.Config.model_validate({**env.config.model_dump(), **settings})
