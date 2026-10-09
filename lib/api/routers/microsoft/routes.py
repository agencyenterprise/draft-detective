"""Everything Draft Detective does inside Microsoft 365, under one prefix.

Two surfaces, split by what they can do rather than by product:

- ``/word`` serves the add-in, which is the only client that can write into a
  document while someone has it open, including the changes asked for in Teams.
- ``/teams`` answers questions about a document the service loads itself, and
  writes nothing, because a server-side write is refused with 423 while the
  document is open.

They share a prefix because they share a tenant, an identity model and a set of
documents, and because a caller reasoning about permissions wants to see them
together.
"""

from fastapi import APIRouter

from lib.api.routers.microsoft import teams, word

router = APIRouter(prefix="/api/microsoft")
router.include_router(word.router)
router.include_router(teams.router)
