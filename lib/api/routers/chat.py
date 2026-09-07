"""Everything the /chat page needs from the backend, scoped to the signed-in user.

Two halves in one router. Persistence backs the assistant-ui thread list and
message history: threads and their stored messages. The agent-facing half is
what talks to a model on the page's behalf: the model picker, the skill list for
slash commands, the streamed turn itself, thread titles, and attachment text.
"""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from lib.agents.chat_agent import (
    CHAT_MODELS,
    DEFAULT_CHAT_MODEL,
    build_chat_agent,
    build_chat_input,
    chat_run_config,
    chat_skill_catalogue,
    resolve_chat_model,
)
from lib.api.auth import get_current_user
from lib.models.chat_thread import ChatMessage, ChatThread
from lib.models.user import User
from lib.services import chat_thread_service
from lib.services.chat.events import stream_chat_events
from lib.services.chat.extract import (
    EmptyDocumentError,
    UnsupportedDocumentError,
    extract_markdown,
)
from lib.services.chat.messages import ChatTurnMessage, to_langchain_messages
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


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    parent_id: Optional[str]
    content: dict[str, Any]


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None


class UpdateThreadRequest(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None


class AppendMessageRequest(BaseModel):
    message_id: str
    parent_id: Optional[str] = None
    content: dict[str, Any] = Field(
        description="The assistant-ui ExportedMessageRepositoryItem JSON"
    )


class ChatModelResponse(BaseModel):
    id: str
    name: str
    is_default: bool


class ChatSkillResponse(BaseModel):
    name: str
    description: str


class ChatStreamRequest(BaseModel):
    messages: List[ChatTurnMessage]
    model: Optional[str] = Field(
        default=None, description="A model id from GET /api/chat/models."
    )


class GenerateTitleRequest(BaseModel):
    messages: List[ChatTurnMessage]


class ExtractResponse(BaseModel):
    text: str


# --- Threads and stored messages -------------------------------------------


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
    await chat_thread_service.delete_thread(thread_id=thread_id, user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/threads/{thread_id}/messages", response_model=List[ChatMessageResponse]
)
async def list_messages(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> List[ChatMessage]:
    return list(
        await chat_thread_service.list_messages(
            thread_id=thread_id, user=current_user
        )
    )


@router.post(
    "/threads/{thread_id}/messages", response_model=ChatMessageResponse
)
async def append_message(
    thread_id: uuid.UUID,
    request: AppendMessageRequest,
    current_user: User = Depends(get_current_user),
) -> ChatMessage:
    return await chat_thread_service.append_message(
        thread_id=thread_id,
        user=current_user,
        message_id=request.message_id,
        parent_id=request.parent_id,
        content=request.content,
    )


# --- The agent ---------------------------------------------------------------


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
    """Answer the latest user message, streamed as server-sent events.

    Each ``data:`` frame is one JSON event: ``text`` and ``reasoning`` deltas,
    ``tool`` calls, ``tool_result``s, or a terminal ``error``. Comment lines are
    heartbeats.
    """

    thread = await chat_thread_service.get_thread(thread_id=thread_id, user=current_user)
    try:
        messages = to_langchain_messages(request.messages)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    agent = build_chat_agent(
        resolve_chat_model(request.model), get_user_decrypted_api_key(current_user)
    )
    events = stream_chat_events(
        agent,
        build_chat_input(messages),
        chat_run_config(thread_id=str(thread.id), user_id=str(current_user.id)),
    )
    return StreamingResponse(
        sse_stream(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/threads/{thread_id}/title", response_model=ChatThreadResponse)
async def generate_thread_title(
    thread_id: uuid.UUID,
    request: GenerateTitleRequest,
    current_user: User = Depends(get_current_user),
) -> ChatThread:
    """Generate a title from the opening messages and store it on the thread."""

    await chat_thread_service.get_thread(thread_id=thread_id, user=current_user)
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
