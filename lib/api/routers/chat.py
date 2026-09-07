"""Everything the /chat page needs from the backend, scoped to the signed-in user.

Two halves in one router. The thread index backs the assistant-ui thread list:
``chat_threads`` rows with owner, title and archived flag. The conversation
itself is read from the LangGraph checkpointer, keyed by the thread id. The
agent-facing half is what talks to a model on the page's behalf: the model
picker, the skill list for slash commands, the streamed turn itself, thread
titles, and attachment text.
"""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from lib.agents.chat_agent import (
    CHAT_MODELS,
    DEFAULT_CHAT_MODEL,
    chat_skill_catalogue,
    resolve_chat_model,
    run_chat_turn,
)
from lib.api.auth import get_current_user
from lib.models.chat_thread import ChatThread
from lib.models.user import User
from lib.services import chat_thread_service
from lib.services.chat.extract import (
    EmptyDocumentError,
    UnsupportedDocumentError,
    extract_markdown,
)
from lib.services.chat.history import (
    ChatAttachment,
    delete_thread_state,
    load_thread_messages,
    read_thread_file,
    to_ui_messages,
)
from lib.services.chat.messages import ChatTurnMessage
from lib.services.chat.sse import sse_stream
from lib.services.chat.title import generate_title
from lib.services.users import get_user_decrypted_api_key

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: Optional[str]
    is_archived: bool
    created_at: datetime
    last_updated_at: datetime


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None


class UpdateThreadRequest(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None


class ThreadFileResponse(BaseModel):
    path: str
    content: str


class ChatModelResponse(BaseModel):
    id: str
    name: str
    is_default: bool


class ChatSkillResponse(BaseModel):
    name: str
    description: str


class ChatStreamRequest(BaseModel):
    message: str = Field(default="", description="The user's new message.")
    message_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="The id the page shows the message under; stored as given.",
    )
    attachments: List[ChatAttachment] = Field(
        default_factory=list,
        description="Documents attached to this message, already converted to text.",
    )
    model: Optional[str] = Field(
        default=None, description="A model id from GET /api/chat/models."
    )


class GenerateTitleRequest(BaseModel):
    messages: List[ChatTurnMessage]


class ExtractResponse(BaseModel):
    text: str


# --- Thread index ------------------------------------------------------------


@router.get("/threads", response_model=List[ChatThreadResponse])
async def list_threads(
    current_user: User = Depends(get_current_user),
) -> List[ChatThread]:
    return list(await chat_thread_service.list_threads(user=current_user))


@router.post("/threads", response_model=ChatThreadResponse)
async def create_thread(
    request: CreateThreadRequest,
    current_user: User = Depends(get_current_user),
) -> ChatThread:
    return await chat_thread_service.create_thread(
        user=current_user, title=request.title
    )


@router.patch("/threads/{thread_id}", response_model=ChatThreadResponse)
async def update_thread(
    thread_id: uuid.UUID,
    request: UpdateThreadRequest,
    current_user: User = Depends(get_current_user),
) -> ChatThread:
    thread: Optional[ChatThread] = None
    if request.title is not None:
        thread = await chat_thread_service.rename_thread(
            thread_id=thread_id, user=current_user, title=request.title
        )
    if request.is_archived is not None:
        thread = await chat_thread_service.set_archived(
            thread_id=thread_id, user=current_user, is_archived=request.is_archived
        )
    if thread is None:
        thread = await chat_thread_service.get_thread(
            thread_id=thread_id, user=current_user
        )
    return thread


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Remove the index row and the checkpointed conversation behind it."""

    await chat_thread_service.delete_thread(thread_id=thread_id, user=current_user)
    await delete_thread_state(str(thread_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- The conversation ----------------------------------------------------------


@router.get("/threads/{thread_id}/messages", response_model=List[dict[str, Any]])
async def list_messages(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> List[dict[str, Any]]:
    """The thread's messages from the checkpointer, in the shape the page renders."""

    await chat_thread_service.get_thread(thread_id=thread_id, user=current_user)
    return to_ui_messages(await load_thread_messages(str(thread_id)))


@router.get("/threads/{thread_id}/files", response_model=ThreadFileResponse)
async def read_thread_file_content(
    thread_id: uuid.UUID,
    path: str = Query(description="A path in the thread's filesystem, e.g. /attachments/draft.md"),
    current_user: User = Depends(get_current_user),
) -> ThreadFileResponse:
    """A file from the agent's filesystem for this thread, such as an attachment."""

    await chat_thread_service.get_thread(thread_id=thread_id, user=current_user)
    content = await read_thread_file(str(thread_id), path)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return ThreadFileResponse(path=path, content=content)


@router.post(
    "/threads/{thread_id}/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_chat_turn(
    thread_id: uuid.UUID,
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Answer a new user message, streamed as server-sent events.

    The thread's history is the checkpointer's; only the new message travels.
    Each ``data:`` frame is one JSON event: ``text`` and ``reasoning`` deltas,
    ``tool`` calls, ``tool_result``s, or a terminal ``error``. Comment lines are
    heartbeats.
    """

    if not request.message.strip() and not request.attachments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A message needs text or an attachment.",
        )
    thread = await chat_thread_service.touch_thread(thread_id=thread_id, user=current_user)

    events = run_chat_turn(
        thread_id=str(thread.id),
        user_id=str(current_user.id),
        model=resolve_chat_model(request.model),
        api_key=get_user_decrypted_api_key(current_user),
        text=request.message,
        attachments=request.attachments,
        message_id=request.message_id,
    )
    return StreamingResponse(
        sse_stream(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- Catalogues, titles, attachments -------------------------------------------


@router.get("/models", response_model=List[ChatModelResponse])
async def list_chat_models(
    _current_user: User = Depends(get_current_user),
) -> List[ChatModelResponse]:
    return [
        ChatModelResponse(
            id=option.id,
            name=option.name,
            is_default=option.model == DEFAULT_CHAT_MODEL,
        )
        for option in CHAT_MODELS
    ]


@router.get("/skills", response_model=List[ChatSkillResponse])
async def list_chat_skills(
    _current_user: User = Depends(get_current_user),
) -> List[ChatSkillResponse]:
    return [
        ChatSkillResponse(name=skill.name, description=skill.description)
        for skill in chat_skill_catalogue()
    ]


@router.post("/threads/{thread_id}/title", response_model=ChatThreadResponse)
async def generate_thread_title(
    thread_id: uuid.UUID,
    request: GenerateTitleRequest,
    current_user: User = Depends(get_current_user),
) -> ChatThread:
    """Generate a title from the opening messages and store it on the thread.

    Idempotent: a thread that already has a title keeps it. assistant-ui asks
    for a title around the end of a thread's first run, sometimes more than once.
    """

    thread = await chat_thread_service.get_thread(thread_id=thread_id, user=current_user)
    if thread.title:
        return thread
    title = await generate_title(
        request.messages, get_user_decrypted_api_key(current_user)
    )
    return await chat_thread_service.rename_thread(
        thread_id=thread_id, user=current_user, title=title
    )


@router.post("/extract", response_model=ExtractResponse)
async def extract_attachment_text(
    file: UploadFile,
    _current_user: User = Depends(get_current_user),
) -> ExtractResponse:
    """Markdown text of an attached PDF or DOCX, for the message that sends it."""

    try:
        text = await extract_markdown(file.filename or "", await file.read())
    except UnsupportedDocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(error)
        ) from error
    except EmptyDocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return ExtractResponse(text=text)
