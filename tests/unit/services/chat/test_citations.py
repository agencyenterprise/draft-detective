"""OpenAI's file-citation tokens become plain references, whole or streamed."""

from langchain_core.messages import AIMessage, AIMessageChunk

from lib.services.chat.citations import (
    END,
    SEPARATOR,
    START,
    CitationFilter,
    render_citation,
    render_citations,
)
from lib.services.chat.events import GraphEventMapper
from lib.services.chat.history import to_ui_messages

CITE = f"{START}filecite{SEPARATOR}/attachments/USAF-Readiness.md{SEPARATOR}L3-L9{END}"


class TestRenderCitation:
    def test_a_file_and_line_range_read_as_prose(self) -> None:
        assert render_citation(f"filecite{SEPARATOR}/attachments/USAF-Readiness.md{SEPARATOR}L3-L9") == (
            "(USAF-Readiness.md, lines 3–9)"
        )
        assert render_citation(f"filecite{SEPARATOR}/attachments/a.md{SEPARATOR}L7") == "(a.md, line 7)"
        assert render_citation(f"filecite{SEPARATOR}/attachments/a.md{SEPARATOR}L7-L7") == "(a.md, line 7)"
        assert render_citation(f"filecite{SEPARATOR}/attachments/a.md") == "(a.md)"

    def test_unknown_payloads_are_dropped(self) -> None:
        assert render_citation("turn0search1") == ""
        assert render_citation(f"cite{SEPARATOR}turn0file0") == ""
        assert render_citation("") == ""

    def test_whole_text_is_rewritten_in_place(self) -> None:
        text = f"Europe. {CITE} {CITE}"
        assert render_citations(text) == (
            "Europe. (USAF-Readiness.md, lines 3–9) (USAF-Readiness.md, lines 3–9)"
        )
        assert render_citations("no markers here") == "no markers here"


class TestCitationFilter:
    def test_a_marker_split_across_chunks_is_held_back_then_rendered(self) -> None:
        pieces = ["Europe. ", START, "filecite", SEPARATOR, "/attachments/a.md", SEPARATOR, "L3-L9", END, " Next."]
        citations = CitationFilter()
        out = [citations.feed(piece) for piece in pieces]
        assert out == ["Europe. ", "", "", "", "", "", "", "(a.md, lines 3–9)", " Next."]
        assert citations.flush() == ""

    def test_an_unterminated_marker_is_rendered_on_flush(self) -> None:
        citations = CitationFilter()
        assert citations.feed(f"See {START}filecite{SEPARATOR}/attachments/a.md{SEPARATOR}L2") == "See "
        assert citations.flush() == "(a.md, line 2)"

    def test_an_unterminated_unknown_marker_is_dropped_on_flush(self) -> None:
        citations = CitationFilter()
        assert citations.feed(f"tail {START}cite{SEPARATOR}turn0") == "tail "
        assert citations.flush() == ""


class TestThroughTheMapperAndHistory:
    def test_streamed_deltas_come_out_rewritten(self) -> None:
        mapper = GraphEventMapper()
        chunks = ["Europe. ", START + "filecite" + SEPARATOR, "/attachments/a.md" + SEPARATOR + "L3-L9" + END + " Done."]
        events: list[dict] = []
        for chunk in chunks:
            events += mapper.map("messages", (AIMessageChunk(content=[{"type": "text", "text": chunk}], id="resp_1"), {}))
        assert [e["v"] for e in events if e["t"] == "text"] == ["Europe. ", "(a.md, lines 3–9) Done."]

    def test_text_held_back_at_the_end_is_released_before_the_message_closes(self) -> None:
        mapper = GraphEventMapper()
        mapper.map("messages", (AIMessageChunk(content=[{"type": "text", "text": f"See {START}filecite{SEPARATOR}/attachments/a.md{SEPARATOR}L2"}], id="resp_1"), {}))
        closing = mapper.map("updates", {"model": {"messages": [AIMessage(content="See ...", id="resp_1")]}})
        assert [e["t"] for e in closing] == ["text", "message_end"]
        assert closing[0]["v"] == "(a.md, line 2)"

    def test_stored_history_is_rewritten_too(self) -> None:
        message = AIMessage(id="a1", content=[{"type": "text", "text": f"Europe. {CITE}"}])
        (ui,) = to_ui_messages([message])
        assert ui["content"] == [{"type": "text", "text": "Europe. (USAF-Readiness.md, lines 3–9)"}]
