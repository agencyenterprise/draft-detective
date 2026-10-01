"""The overview reads its runs before its issues_version.

A finishing run commits its issues before it marks itself completed. Reading
the runs first therefore guarantees a completed run never comes with an
issues_version that predates its findings, which would leave the client
holding stale issues once it stops polling.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.project import AccessLevel, Project
from lib.services import project_overview
from lib.services.project_overview import _OverviewRuns, get_project_overview


@pytest.mark.asyncio
async def test_issues_version_is_read_only_after_the_runs():
    order: list[str] = []

    async def runs(*_: object) -> _OverviewRuns:
        order.append("runs:start")
        # Yield, so a concurrent issues read would get in before this finishes.
        await asyncio.sleep(0)
        order.append("runs:end")
        return _OverviewRuns(summaries=[])

    async def issues_version(*_: object) -> str:
        order.append("issues_version")
        return "0::"

    project = Project(id=uuid.uuid4(), title="p", current_revision=1)
    with (
        patch.object(project_overview, "_overview_runs", side_effect=runs),
        patch.object(
            project_overview, "get_issues_version", side_effect=issues_version
        ),
        patch.object(
            project_overview,
            "get_project_files_list_items",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(
            project_overview, "_owner_share_status", new=AsyncMock(return_value=None)
        ),
    ):
        await get_project_overview(project, AccessLevel.WRITE)

    assert order == ["runs:start", "runs:end", "issues_version"]
