"""Tests for the tools that open and check SharePoint documents.

Four things carry weight here.

A document must be *mounted* rather than returned, because a tool result over roughly
80,000 characters is evicted to a machine-named file, and real documents run to that size.

The agent chooses the path, so the path must be **validated**: ``files`` is one namespace
shared with ``/skills/``, and a path of ``/skills/issues/SKILL.md`` would overwrite the
instructions the agent is following.

A link must remain the only way in: there is deliberately no lookup by name, so a name
cannot reach a document the person asking could not already open.

And both tools must carry the identity they were built with all the way to Graph -- that
token is what makes the bot no more privileged than the asker, so losing it is a security
regression rather than a bug in a feature.
"""

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from deepagents.backends.utils import file_data_to_string
from langgraph.types import Command

from lib.agents.tools import sharepoint
from lib.services.microsoft.graph.client import DocumentNotAllowed, GraphError
from lib.services.microsoft.graph.documents import LoadedDocument

TOKEN = "a-user-token"
PATH = "/documents/v2-cern-for-ai.md"


def opener(token: str = TOKEN) -> Any:
    """The tool as a run gets it: built for one identity."""

    return sharepoint.open_document_for(token)


def checker(token: str = TOKEN) -> Any:
    return sharepoint.check_document_for(token)


async def call(tool: Any, *args: Any) -> Any:
    """Invoke a tool's coroutine directly, bypassing its argument schema.

    The same shortcut ``test_vector_search.py`` takes. Typed loosely on purpose: the
    alternative is an ``attr-defined`` ignore at every call site, because ``@tool``
    returns a ``BaseTool`` whose ``coroutine`` mypy cannot see.
    """

    return await tool.coroutine(*args)


def mounted(result: Any) -> dict[str, Any]:
    """The files a Command mounts, having checked it is a Command that mounts some."""

    assert isinstance(
        result, Command
    ), f"expected a Command, got {type(result).__name__}: {result}"
    assert result.update is not None, "a Command that updates nothing mounts nothing"
    return dict(result.update["files"])


def body_of(files: dict[str, Any], path: str) -> str:
    """A mounted file's text."""

    return file_data_to_string(files[path])


def message_of(result: Any) -> str:
    """What the model is told a Command did."""

    assert isinstance(result, Command)
    assert result.update is not None
    return str(result.update["messages"][0].content)


def runtime() -> MagicMock:
    """A tool runtime, which only needs to carry the call id."""

    fake = MagicMock()
    fake.tool_call_id = "call_abc123"
    return fake


def document(
    markdown: Optional[str] = None,
    comments: Optional[list[tuple[str, str]]] = None,
) -> LoadedDocument:
    return LoadedDocument(
        name="v2-cern-for-ai.docx",
        url="https://x.sharepoint.com/sites/X/Shared%20Documents/v2-cern-for-ai.docx",
        markdown=(
            markdown if markdown is not None else "## A heading\n\nFirst.\n\nSecond."
        ),
        comments=comments or [],
        last_modified="2026-08-04T13:31:28Z",
        size_bytes=180097,
    )


def loading(document_or_error: Any) -> Any:
    """Patch ``documents.load`` with a result or a failure."""

    if isinstance(document_or_error, BaseException):
        return patch.object(
            sharepoint.documents, "load", AsyncMock(side_effect=document_or_error)
        )
    return patch.object(
        sharepoint.documents, "load", AsyncMock(return_value=document_or_error)
    )


class TestOpeningADocument:
    @pytest.mark.asyncio
    async def test_the_document_is_mounted_where_the_agent_asked(self) -> None:
        with loading(document()):
            result = await call(opener(), "https://x/a.docx", PATH, runtime())

        assert PATH in mounted(result)

    @pytest.mark.asyncio
    async def test_the_mounted_text_keeps_the_document_structure(self) -> None:
        """Markdown, not a flat list of paragraphs.

        Headings and tables are how the agent navigates and how a skill tells one part of
        a document from another, so losing them is the regression this guards.
        """

        markdown = (
            "## Abbreviations\n\n| AI | artificial intelligence |\n\nBody **text**."
        )
        with loading(document(markdown)):
            result = await call(opener(), "https://x/a.docx", PATH, runtime())

        assert body_of(mounted(result), PATH) == markdown

    @pytest.mark.asyncio
    async def test_nothing_is_prefixed_onto_the_lines(self) -> None:
        """The read tool numbers lines itself, so a second scheme only competes."""

        with loading(document("Alpha.\n\nBeta.")):
            result = await call(opener(), "https://x/a.docx", PATH, runtime())

        body = body_of(mounted(result), PATH)
        assert "[0]" not in body and "[1]" not in body

    @pytest.mark.asyncio
    async def test_the_body_is_not_in_the_tool_message(self) -> None:
        """A result carrying the body would be evicted to a machine-named file."""

        with loading(document("A distinctive sentence.")):
            result = await call(opener(), "https://x/a.docx", PATH, runtime())

        message = message_of(result)
        assert "distinctive sentence" not in message
        assert "1 lines" in message and PATH in message

    @pytest.mark.asyncio
    async def test_the_modified_time_is_reported_so_it_can_be_compared_later(
        self,
    ) -> None:
        """``check_document`` is only useful against a time the agent already has."""

        with loading(document()):
            result = await call(opener(), "https://x/a.docx", PATH, runtime())

        assert "2026-08-04T13:31:28Z" in message_of(result)

    @pytest.mark.asyncio
    async def test_comments_are_mounted_beside_the_document(self) -> None:
        with loading(document(comments=[("Carlos", "is this right?")])):
            result = await call(opener(), "https://x/a.docx", PATH, runtime())

        files = mounted(result)
        beside = "/documents/v2-cern-for-ai.comments.md"
        assert beside in files
        assert "Carlos: is this right?" in body_of(files, beside)

    @pytest.mark.asyncio
    async def test_each_document_gets_its_own_comments_file(self) -> None:
        """One shared comments file would answer about one document from another's."""

        with loading(document(comments=[("Carlos", "on v2")])):
            first = mounted(await call(opener(), "https://x/v2.docx", PATH, runtime()))
        with loading(document(comments=[("Ana", "on v3")])):
            second = mounted(
                await call(opener(), "https://x/v3.docx", "/documents/v3.md", runtime())
            )

        assert set(first) & set(second) == set(), "no path is shared between the two"

    @pytest.mark.asyncio
    async def test_no_comments_clears_any_previous_ones(self) -> None:
        """A ``None`` is the reducer's delete, not an oversight.

        Re-opening a document whose comments have been resolved must not keep answering
        from the ones it had before.
        """

        with loading(document()):
            result = await call(opener(), "https://x/a.docx", PATH, runtime())

        assert mounted(result)["/documents/v2-cern-for-ai.comments.md"] is None

    @pytest.mark.asyncio
    async def test_a_document_outside_the_allowlist_is_refused_in_words(self) -> None:
        """The model has to be able to explain the refusal, so it gets a string."""

        with loading(DocumentNotAllowed("evil.com is not allowed")):
            result = await call(opener(), "https://evil.com/a.docx", PATH, runtime())

        assert isinstance(result, str)
        assert "not allowed" in result

    @pytest.mark.asyncio
    async def test_an_unexpected_failure_is_reported_not_raised(self) -> None:
        with loading(RuntimeError("boom")):
            result = await call(opener(), "https://x/a.docx", PATH, runtime())

        assert isinstance(result, str) and "boom" in result


class TestChoosingWhereItGoes:
    """The path comes from the model, so it is validated rather than trusted.

    ``files`` is a single namespace holding the skills as well as the documents, so an
    unchecked path is a way for the agent to overwrite its own instructions.
    """

    def test_a_bare_name_is_placed_under_the_documents_prefix(self) -> None:
        assert sharepoint.document_path("v3.md") == "/documents/v3.md"

    def test_a_path_that_is_already_right_is_left_alone(self) -> None:
        assert sharepoint.document_path("/documents/v3.md") == "/documents/v3.md"

    def test_spaces_and_brackets_in_a_document_name_are_allowed(self) -> None:
        """Real file names have them, and refusing would be a nuisance for no gain."""

        assert sharepoint.document_path("/documents/v3-cern (final).md") == (
            "/documents/v3-cern (final).md"
        )

    @pytest.mark.parametrize(
        "path",
        [
            "/skills/issues/SKILL.md",
            "/main.md",
            "/documents/sub/x.md",
            "../../etc/passwd.md",
            "/documents/x.txt",
            "/documents/.hidden.md",
        ],
        ids=[
            "over a skill",
            "outside the prefix",
            "nested",
            "traversal",
            "not markdown",
            "a dotfile",
        ],
    )
    def test_anything_that_would_land_elsewhere_is_refused(self, path: str) -> None:
        with pytest.raises(ValueError):
            sharepoint.document_path(path)

    @pytest.mark.asyncio
    async def test_a_bad_path_is_explained_rather_than_raised(self) -> None:
        """The model can correct itself from the message; an exception ends the run."""

        load = AsyncMock(return_value=document())
        with patch.object(sharepoint.documents, "load", load):
            result = await call(
                opener(), "https://x/a.docx", "/skills/issues/SKILL.md", runtime()
            )

        assert isinstance(result, str)
        assert "/documents/" in result
        assert load.await_count == 0, "refused before anything was downloaded"


class TestCheckingADocument:
    """The cheap counterpart: has it changed, and may this person still read it.

    Both questions matter because a conversation persists -- a mounted document may have
    been edited since, and may have been opened for somebody else in the thread.
    """

    def resolving(self, item_or_error: Any) -> Any:
        if isinstance(item_or_error, BaseException):
            return patch.object(
                sharepoint.client, "resolve", AsyncMock(side_effect=item_or_error)
            )
        return patch.object(
            sharepoint.client, "resolve", AsyncMock(return_value=item_or_error)
        )

    @pytest.mark.asyncio
    async def test_it_reports_the_name_and_when_it_changed(self) -> None:
        with self.resolving(
            {"name": "v3.docx", "lastModifiedDateTime": "2026-08-13T09:00:00Z"}
        ):
            result = await call(checker(), "https://x/v3.docx")

        assert "v3.docx" in result and "2026-08-13T09:00:00Z" in result

    @pytest.mark.asyncio
    async def test_it_does_not_download_the_document(self) -> None:
        """The whole point: metadata only, so it is cheap enough to call every turn."""

        load = AsyncMock()
        with self.resolving({"name": "v3.docx", "lastModifiedDateTime": "x"}):
            with patch.object(sharepoint.documents, "load", load):
                await call(checker(), "https://x/v3.docx")

        assert load.await_count == 0

    @pytest.mark.asyncio
    async def test_it_asks_as_the_person_who_asked(self) -> None:
        """Which is what makes a refusal here mean something about *their* access."""

        resolve = AsyncMock(return_value={"name": "v3.docx"})
        with patch.object(sharepoint.client, "resolve", resolve):
            await call(checker("carlos-token"), "https://x/v3.docx")

        assert resolve.await_args is not None
        assert resolve.await_args.kwargs["token"] == "carlos-token"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "failure",
        [
            GraphError("could not find v3.docx: 403"),
            DocumentNotAllowed("outside the site paths this service may read"),
        ],
        ids=["graph refuses this person", "outside the allowlist"],
    )
    async def test_a_refusal_comes_back_as_words(self, failure: Exception) -> None:
        with self.resolving(failure):
            result = await call(checker(), "https://x/v3.docx")

        assert isinstance(result, str)
        assert "not allowed" in result or "could not check" in result

    @pytest.mark.asyncio
    async def test_a_document_with_no_edit_time_still_confirms_access(self) -> None:
        with self.resolving({"name": "v3.docx"}):
            result = await call(checker(), "https://x/v3.docx")

        assert "you can read it" in result


class TestALinkIsTheOnlyWayIn:
    def test_there_is_no_tool_that_looks_a_document_up_by_name(self) -> None:
        """Removed on purpose, so this guards against it coming back unnoticed.

        Searching for a name means searching somewhere, and anything the service can
        search is wider than what the person asking may be allowed to read.
        """

        assert not hasattr(sharepoint, "find_document")

    def test_the_tool_tells_the_model_a_link_is_required(self) -> None:
        """Otherwise the model invents a URL when it is only given a name."""

        assert "no way to look a document up by name" in (opener().description or "")


class TestWhoseAccessIsUsed:
    """The token a tool was built with is what limits what a run can read.

    It is the asker's, so Graph refuses a document they cannot open. It must reach Graph
    unchanged from the tool, or a read would no longer be limited to what they can open.
    """

    @pytest.mark.asyncio
    async def test_the_token_reaches_the_loader(self) -> None:
        load = AsyncMock(return_value=document())
        with patch.object(sharepoint.documents, "load", load):
            await call(opener("carlos-token"), "https://x/a.docx", PATH, runtime())

        assert load.await_args is not None
        assert load.await_args.kwargs["token"] == "carlos-token"

    @pytest.mark.asyncio
    async def test_two_tools_do_not_share_an_identity(self) -> None:
        """One process serves many askers, so the binding has to be per tool."""

        load = AsyncMock(return_value=document())
        with patch.object(sharepoint.documents, "load", load):
            await call(opener("first-user"), "https://x/a.docx", PATH, runtime())
            await call(opener("second-user"), "https://x/a.docx", PATH, runtime())

        used = [call_.kwargs["token"] for call_ in load.await_args_list]
        assert used == ["first-user", "second-user"]

    @pytest.mark.asyncio
    async def test_a_refusal_for_this_user_is_explained_not_retried(self) -> None:
        """Graph answers 403 when the asker cannot open it. That is the check working."""

        with loading(GraphError("could not download a.docx: 403")):
            result = await call(opener(), "https://x/a.docx", PATH, runtime())

        assert isinstance(result, str) and "403" in result

    def test_the_model_is_told_it_reads_as_the_asker(self) -> None:
        """So a refusal is reported rather than worked around."""

        assert "as the person who asked" in (opener().description or "")

    def test_the_checker_is_told_a_refusal_is_about_the_asker(self) -> None:
        """Or a refused check reads as a broken tool rather than an answer."""

        assert "cannot read it" in (checker().description or "")


class TestTheToolSchemas:
    def test_the_runtime_and_the_token_are_hidden_from_the_model(self) -> None:
        """The runtime is injected by LangChain; the token is closed over.

        Neither belongs in the schema. A token the model could see is a token it could
        put in an answer.
        """

        assert list(opener().args) == ["url", "path"]
        assert list(checker().args) == ["url"]

    def test_both_tools_document_themselves(self) -> None:
        """The model picks a tool from its description, so an empty one is a bug."""

        for tool in (opener(), checker()):
            description = tool.description
            assert description and len(description) > 80
            assert TOKEN not in description
