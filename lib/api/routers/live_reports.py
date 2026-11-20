"""What the /live-reports page needs beyond /chat's endpoints.

A live report is a ``chat_threads`` row of kind ``live_report``: it is created,
listed, streamed and read back through ``/api/chat``. The one thing /chat has no
endpoint for is the files the orchestrator writes for the user to review, the
skill's step files under ``/live-report/``.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from lib.agents.live_report_agent import LIVE_REPORT_DIR
from lib.agents.thread_agents import thread_agent
from lib.api.auth import get_current_user
from lib.models.chat_thread import ChatThreadKind
from lib.models.user import User
from lib.services import chat_thread_service
from lib.services.chat.thread_state import list_thread_files

router = APIRouter(prefix="/api/live-reports", tags=["live-reports"])


class LiveReportFileResponse(BaseModel):
    """One of the files, as it stands now. ``name`` is relative to the live
    report's folder: ``intake.md``, or ``research/F1.md`` for a research note."""

    name: str
    content: str


@router.get("/{thread_id}/files", response_model=list[LiveReportFileResponse])
async def list_live_report_files(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> list[LiveReportFileResponse]:
    """The files written so far: the step files (``intake.md``,
    ``research-plan.md``…) and the research notes under ``research/``, which the
    page uses to show the research's progress.
    """

    thread = await chat_thread_service.get_thread(
        thread_id=thread_id, user=current_user
    )
    if thread.kind != ChatThreadKind.LIVE_REPORT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Live report not found"
        )
    files = await list_thread_files(
        str(thread_id),
        LIVE_REPORT_DIR,
        reader=thread_agent(thread.kind).reader,
        recursive=True,
    )
    prefix = LIVE_REPORT_DIR.rstrip("/") + "/"
    return [
        LiveReportFileResponse(name=path.removeprefix(prefix), content=content)
        for path, content in files.items()
    ]
