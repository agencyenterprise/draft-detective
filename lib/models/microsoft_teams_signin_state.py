"""Questions waiting for their askers to sign in to the Teams bot.

A question from someone the bot has no token for is parked here while they sign in, and
taken back out by the card action that follows -- a different request, usually on a
different worker. Production runs Uvicorn with ``--workers 4`` (``Dockerfile`` and
``railway.toml``), so this cannot live in process memory. Same shape of problem as the
one ``mcp_oauth_kv`` exists for, and a separate table because this is a different
subsystem with a different lifetime.

Rows are short lived: a question is removed when it is answered. One whose asker never
finishes signing in is never taken back, so
``lib/services/microsoft/teams/pending_questions.py`` sweeps rows left untouched for an
hour every time a question is parked. That matters because what is
stored is the question, text and sender included, and this table is not the place for
it to accumulate.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class MicrosoftTeamsSignInState(SQLModel, table=True):
    __tablename__ = "microsoft_teams_signin_state"

    key: str = Field(
        sa_column=Column(String, primary_key=True),
        description=(
            "The id the sign-in card carries."
        ),
    )
    value: dict = Field(
        sa_column=Column(JSONB, nullable=False),
        description=(
            "The parked question: its text, who asked, the links it carried and where "
            "to post the answer. No token -- those live in the Bot Framework token "
            "service, never here."
        ),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description=(
            "When this row was last written. Indexed because the sweep filters on it: "
            "a write deletes rows left untouched past the abandonment window."
        ),
    )
