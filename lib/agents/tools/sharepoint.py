"""Opening SharePoint documents mid-run.

An agent answering a question from Teams is not told which document to read. It is given
the links found in the message and decides which to open, where to put it, and whether
what it already has is still good enough.

Only from a link. Finding a document by name was built and removed: matching names
means searching somewhere, and anything the service can search is wider than what the
person asking may be allowed to read. A link is something they already had.

Both tools are built per run, bound to one identity, by the factories below. That is
deliberate: the token belongs to the person who asked, so a run cannot read anything they
could not. The model never sees the token -- it is closed over, not a parameter.

``open_document`` mounts the document rather than returning its text, because a tool
result over roughly 80,000 characters is evicted by the filesystem middleware to
``/large_tool_results/{tool_call_id}``, and real documents here run to that size. The
agent chooses the path, under ``DOCUMENTS`` so that one thread can hold several documents
-- two revisions, or two different files -- without them overwriting each other.

``check_document`` is the cheap counterpart: metadata only, no download. It answers
whether a document has changed since the agent last read it, and because Graph applies
the asker's own permissions to the lookup, a refusal answers whether *this* person may
read it at all. Both matter across turns: a conversation persists, so a mounted document
may have been edited since, and may have been loaded for somebody else in the thread.
"""

import logging
import re
from typing import Any, Optional

from deepagents.backends.utils import create_file_data
from deepagents.middleware.filesystem import FilesystemState
from langchain.tools import BaseTool, ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from lib.services.microsoft.graph import client, documents
from lib.services.microsoft.graph.client import (
    DocumentNotAllowed,
    GraphError,
    redacted,
)

logger = logging.getLogger(__name__)

# Documents live under one prefix so a model-chosen path cannot land anywhere else --
# most of all not over a skill, which shares this filesystem and is the agent's own
# instructions.
DOCUMENTS = "/documents"

_SAFE_NAME = re.compile(r"^[\w][\w .()-]*$")


def document_path(path: str) -> str:
    """The mount path for a document, or a refusal explaining the convention.

    Raises ``ValueError`` with something the model can act on. Validated rather than
    trusted because ``files`` is one namespace shared with ``/skills/``: a path of
    ``/skills/issues/SKILL.md`` would overwrite the instructions the agent is following.
    """

    # A bare name is accepted and placed under the prefix; anything that would land
    # elsewhere is refused rather than quietly relocated.
    name = path.strip().removeprefix(f"{DOCUMENTS}/")
    if "/" in name:
        raise ValueError(
            f"paths must be directly under {DOCUMENTS}/, like {DOCUMENTS}/v3.md"
        )
    if not name.endswith(".md"):
        raise ValueError(f"the path must end in .md, like {DOCUMENTS}/v3.md")
    if not _SAFE_NAME.match(name.removesuffix(".md")):
        raise ValueError(
            "the file name may only contain letters, numbers, spaces, dots, dashes, "
            "brackets and underscores"
        )
    return f"{DOCUMENTS}/{name}"


def comments_path(path: str) -> str:
    """Where a document's comments go: beside it, named after it.

    Per document rather than one shared file, so a thread holding two documents cannot
    answer about one from the other's comments.
    """

    return f"{path.removesuffix('.md')}.comments.md"


def open_document_for(token: str) -> BaseTool:
    """The document-opening tool, reading as whoever ``token`` belongs to."""

    @tool()
    async def open_document(
        url: str, path: str, runtime: ToolRuntime[Any, FilesystemState]
    ) -> Command | str:
        """
        Open a Word document from a SharePoint link so you can read it.

        The document is saved as markdown at the path you choose, with its headings,
        tables and emphasis intact. Any comments on it are saved alongside, at the same
        path with `.comments.md` instead of `.md`. Use your read and search tools on
        those files; this tool does not return the text.

        You open it as the person who asked, so a document they cannot access will be
        refused. Tell them that plainly rather than trying another way in.

        There is no way to look a document up by name: without a link, ask for one.

        Args:
            url: The document's SharePoint link, as pasted by the person asking.
            path: Where to save it, directly under /documents/ and ending in .md — for
                example /documents/v3-cern-for-ai.md. Name it after the document so you
                can tell them apart later. Opening two documents, or two revisions of
                one, means two different paths. Re-opening the same document at the same
                path replaces it, which is how you refresh a stale copy.

        Returns:
            A confirmation of what was opened and where. Example:
            Opened 'v3-cern-for-ai.docx' at /documents/v3-cern-for-ai.md: 648 lines.
            Modified 2026-08-07T17:56:47Z.
        """

        try:
            destination = document_path(path)
        except ValueError as error:
            return f"I could not save it there: {error}"

        try:
            document = await documents.load(url, token=token)
        except DocumentNotAllowed as error:
            return f"I am not allowed to read that document: {error}"
        except GraphError as error:
            logger.error("could not open %s: %s", redacted(url), error)
            return f"I could not open that document: {error}"
        except Exception as error:  # noqa: BLE001 - the model decides what to do next
            logger.exception("could not open %s", redacted(url))
            return f"I could not open that document: {error}"

        logger.info("opened %s at %s", redacted(url), destination)

        # A Command is how a tool writes into the agent's filesystem; the built-in
        # write_file does the same. The files key merges, so this adds rather than
        # replaces, and mounting the same path twice overwrites it.
        return Command(
            update={
                "files": document_files(document, destination),
                "messages": [
                    ToolMessage(
                        content=describe(document, destination),
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    return open_document


def check_document_for(token: str) -> BaseTool:
    """The freshness-and-access tool, asking as whoever ``token`` belongs to."""

    @tool()
    async def check_document(url: str) -> str:
        """
        Check when a document was last changed, without downloading it.

        Cheap: this reads only the document's details, not its contents. Use it on a
        document you opened in an earlier turn to find out whether it has been edited
        since — compare the time it returns with the time reported when you opened it.

        It also answers whether the person asking now can reach the document at all,
        because it looks it up as them. A refusal here means they cannot read it, so do
        not answer from a copy you opened earlier for somebody else.

        Args:
            url: The document's SharePoint link.

        Returns:
            The document's name and when it was last modified. Example:
            'v3-cern-for-ai.docx' was last modified 2026-08-07T17:56:47Z.
        """

        try:
            item = await client.resolve(url, token=token)
        except DocumentNotAllowed as error:
            return f"I am not allowed to read that document: {error}"
        except GraphError as error:
            logger.info("could not check %s: %s", redacted(url), error)
            return f"I could not check that document: {error}"
        except Exception as error:  # noqa: BLE001 - the model decides what to do next
            logger.exception("could not check %s", redacted(url))
            return f"I could not check that document: {error}"

        name = item.get("name") or "the document"
        modified = item.get("lastModifiedDateTime")
        if not modified:
            return f"'{name}' exists and you can read it, but it reports no edit time."
        return f"'{name}' was last modified {modified}."

    return check_document


def document_files(document: documents.LoadedDocument, path: str) -> dict[str, Any]:
    """A document as the agent's filesystem holds it, at ``path``."""

    comments = comments_path(path)
    return {
        path: create_file_data(document.markdown),
        # Cleared when there are none rather than left out: re-opening a document whose
        # comments have been resolved would otherwise keep answering from the old ones.
        comments: (
            create_file_data(format_comments(document.comments))
            if document.comments
            else None
        ),
    }


def format_comments(comments: list[tuple[str, str]]) -> str:
    """The document's existing comments, as a file the agent can read."""

    return "\n\n".join(f"{author}: {text}" for author, text in comments)


def describe(document: documents.LoadedDocument, path: str) -> str:
    """What was opened and where, without any of its content.

    Kept to a summary on purpose: a tool result carrying the body would be evicted to a
    machine-named file and defeat the mounting above. The modified time is included
    because it is what ``check_document`` is later compared against.
    """

    # Lines rather than paragraphs, because that is the unit the read and search tools
    # report positions in -- so the size given here is in the same currency.
    parts = [f"Opened '{document.name}' at {path}: {document.lines} lines"]
    if document.comments:
        parts.append(f", {len(document.comments)} comments at {comments_path(path)}")
    parts.append(".")
    if document.last_modified:
        parts.append(f" Modified {document.last_modified}.")
    return "".join(parts)
