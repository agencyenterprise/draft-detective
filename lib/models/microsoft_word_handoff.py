"""Review work prepared in Teams, waiting to be written into a Word document.

The Teams bot cannot write to a document: SharePoint refuses a whole-file write with
423 while anyone has it open, and a Word desktop session holds that lock for minutes
after it closes. So when someone in Teams asks for comments or tracked changes, the bot
stores them here, and the Word add-in applies them the next time that person opens the
document. ``lib/services/microsoft/word/handoffs.py`` is what reads and writes it.

A handoff belongs to the person who asked. It is released only to an add-in user signed
in with the same Microsoft account -- the same Entra object id, in the same tenant --
which is what makes storing document text here acceptable: nobody can read it back who
did not write the request. Rows are swept a week after they were created, applied or
not.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel


class MicrosoftWordHandoff(SQLModel, table=True):
    __tablename__ = "microsoft_word_handoffs"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    requested_by_oid: str = Field(
        sa_column=Column(String, nullable=False, index=True),
        description=(
            "The asker's Entra object id. The add-in must be signed in as the same "
            "account to see the handoff."
        ),
    )
    requested_by_tid: Optional[str] = Field(
        default=None,
        sa_column=Column(String, nullable=True),
        description="The asker's tenant, when Teams reported it; checked alongside the oid",
    )
    requested_by_upn: str = Field(
        sa_column=Column(String, nullable=False),
        description="The asker's user principal name, for logs and support only",
    )
    document_name: str = Field(sa_column=Column(String, nullable=False))
    document_url: str = Field(
        sa_column=Column(String, nullable=False),
        description="The document's webUrl, for linking to it",
    )
    document_keys: list[str] = Field(
        sa_column=Column(JSONB, nullable=False),
        description=(
            "Every form under which the add-in may report this document's URL: its "
            "SharePoint unique id and its path. See ``handoffs.keys_for_url``."
        ),
    )
    items: dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=False),
        description="The comments and edits to apply, as ``HandoffItems``",
    )
    reference: dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=False),
        description="Where in Teams to report back once it has been applied",
    )
    status: str = Field(
        sa_column=Column(String, nullable=False, default="pending"),
        description="pending, applied or dismissed",
    )
    outcome: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="What the add-in reported: which items landed and which did not",
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    finished_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
