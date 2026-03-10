"""
Test cases demonstrating NLTK sentence tokenization issues with citations in footnotes.

The problem: NLTK's sent_tokenize splits citations incorrectly at periods that are
NOT sentence boundaries (e.g., after author initials, journal abbreviations, etc.)
"""

import pytest
from lib.agents.document_chunker_nltk import split_paragraph_into_sentences
from lib.agents.sentence_tokenizer import SentenceTokenizerAgent
from tests.conftest import create_test_context


class TestCitationTokenization:
    """Test cases showing how NLTK + LLM hybrid approach handles citations."""

    @pytest.mark.asyncio
    async def test_citation_with_author_initials(self):
        """
        Citation with author initials should NOT be split.

        NLTK treats periods after initials (J., A., B.) as sentence boundaries,
        so fragment detection should trigger LLM fallback to keep citation intact.
        """
        citation = "Smith, J., Doe, A., & Roe, B. (2019). A Comprehensive Study of Gizmos. Proceedings of Gizmo Conf."

        result = await split_paragraph_into_sentences(
            citation, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        assert len(result) == 1, f"Expected 1 chunk but got {len(result)}: {result}"
        assert result[0] == citation

    @pytest.mark.asyncio
    async def test_citation_with_et_al(self):
        """
        Citation with 'et al.' should NOT be split at the period.

        NLTK treats 'al.' as a sentence boundary, triggering LLM fallback.
        """
        citation = "Johnson et al. (2020). Machine Learning Approaches to Data Analysis. Nature Machine Intelligence, 5(2), 123-145."

        result = await split_paragraph_into_sentences(
            citation, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        assert len(result) == 1, f"Expected 1 chunk but got {len(result)}: {result}"
        assert result[0] == citation

    @pytest.mark.asyncio
    async def test_citation_with_journal_abbreviation(self):
        """Citation with journal abbreviations should NOT be split."""
        citation = "Brown, M., & Green, K. (2018). Neural Networks in Practice. J. Neurosci. Methods, 15(3), 45-67."

        result = await split_paragraph_into_sentences(
            citation, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        assert len(result) == 1, f"Expected 1 chunk but got {len(result)}: {result}"
        assert result[0] == citation

    @pytest.mark.asyncio
    async def test_citation_with_multiple_sentences_in_abstract(self):
        """
        Numbered references are kept as single chunks.

        Even if they contain descriptive sentences after the citation.
        """
        footnote = "1. Smith, J. (2020). The Effects of Widgets. Journal of Widgetry. This groundbreaking study examined widget performance. Results showed a 20% improvement."

        result = await split_paragraph_into_sentences(
            footnote, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        assert (
            len(result) == 1
        ), f"Expected 1 chunk (numbered ref) but got {len(result)}: {result}"

    @pytest.mark.asyncio
    async def test_mixed_citations_with_initials_and_abbreviations(self):
        """Complex citation with multiple problematic periods should remain intact."""
        citation = "Anderson, R. J., Smith, P. K., & Williams, M. T. (2021). Advanced Topics in A.I. Research. Proc. Natl. Acad. Sci. U.S.A., 118(25), e2021234118."

        result = await split_paragraph_into_sentences(
            citation, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        assert len(result) == 1, f"Expected 1 chunk but got {len(result)}: {result}"
        assert result[0] == citation

    @pytest.mark.asyncio
    async def test_footnote_with_multiple_citations(self):
        """
        Multiple citations should not split within individual citations.

        May split between citations, but never within author names or abbreviations.
        """
        footnote = "See Smith, J. (2020). Widget Analysis. J. Widgets, 5(2), 10-20. See also Doe, A. (2019). Gadget Performance. Tech. Rev., 8(1), 5-15."

        result = await split_paragraph_into_sentences(
            footnote, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        for chunk in result:
            assert len(chunk.split()) > 1, f"Got a fragment chunk: '{chunk}'"

    @pytest.mark.asyncio
    async def test_citation_doi_and_url(self):
        """Modern citations with DOIs should not split at periods in URLs."""
        citation = "Martinez, L. et al. (2022). Deep Learning Applications. Nature, 600, 123-128. https://doi.org/10.1038/s41586-022-12345-6"

        result = await split_paragraph_into_sentences(
            citation, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        assert len(result) == 1, f"Expected 1 chunk but got {len(result)}: {result}"
        assert result[0] == citation

    @pytest.mark.asyncio
    async def test_numbered_footnote_citation(self):
        """Numbered footnotes have special handling to keep them as single chunks."""
        footnote = "1. National Institute of Standards and Technology (NIST). (2022). Security Guidelines. Tech. Rep. 800-53."

        result = await split_paragraph_into_sentences(
            footnote, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        assert len(result) == 1, f"Expected 1 chunk but got {len(result)}: {result}"
        assert result[0] == footnote

    @pytest.mark.asyncio
    async def test_regular_prose_still_splits_correctly(self):
        """Regular prose should still split correctly at sentence boundaries."""
        prose = "This is the first sentence. This is the second sentence. And here is a third."

        result = await split_paragraph_into_sentences(
            prose, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        assert len(result) == 3, f"Expected 3 chunks but got {len(result)}: {result}"
        assert "first sentence" in result[0]
        assert "second sentence" in result[1]
        assert "third" in result[2]

    @pytest.mark.asyncio
    async def test_paragraph_with_inline_markdown_citations(self):
        """
        Paragraph with inline markdown-style citations should NOT split on citation markers.

        This tests the real-world case from RAND documents where paragraphs contain
        inline citations like [[4]](#footnote-3). Citations should stay attached to
        their sentences, not appear as fragments.
        """
        paragraph = (
            "Developing advanced AI models requires enormous amounts of power[[4]](#footnote-3) "
            "and existing facilities are already straining the U.S. electricity grids.[[5]](#footnote-4) "
            "As the demand for computational resources continues to rise, electricity consumption "
            "by AI data centers is expected to grow at an unprecedented rate in the coming years.[[6]](#footnote-5)"
        )

        result = await split_paragraph_into_sentences(
            paragraph, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        # Should be 2 sentences (compound sentence with "and", then a new sentence)
        assert len(result) == 2, f"Expected 2 chunks but got {len(result)}: {result}"

        # First sentence has two citations (compound sentence with "and")
        assert "power[[4]](#footnote-3)" in result[0]
        assert "grids.[[5]](#footnote-4)" in result[0]

        # Second sentence has one citation
        assert "years.[[6]](#footnote-5)" in result[1]

        # Verify no fragment-only chunks (like just a citation marker)
        for chunk in result:
            assert len(chunk) > 20, f"Got suspicious fragment: '{chunk}'"
            # Verify citations are not standalone
            assert not chunk.startswith("[["), f"Citation marker at start: '{chunk}'"

    @pytest.mark.asyncio
    async def test_paragraph_with_multiple_inline_citations_per_sentence(self):
        """
        Sentences with multiple inline citations should stay together.

        Tests the case where a single sentence has multiple citation markers.
        """
        paragraph = (
            "Based on current trends for data center power consumption, estimates for AI load growth "
            "include 63 GW by 2028,[[7]](#footnote-6) and range between 47 GW[[8]](#footnote-7) "
            "to 171 GW by 2030.[[9]](#footnote-8) Beyond the challenge of aggregated scale, a single "
            "site expected to demand a large amount of power also poses issues related to building "
            "necessary infrastructure in a timely manner[[10]](#footnote-9) and maintain grid stability.[[11]](#footnote-10)"
        )

        result = await split_paragraph_into_sentences(
            paragraph, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        # Should be 2 sentences
        assert len(result) == 2, f"Expected 2 chunks but got {len(result)}: {result}"

        # First sentence should have all 3 citations
        assert "[[7]](#footnote-6)" in result[0]
        assert "[[8]](#footnote-7)" in result[0]
        assert "[[9]](#footnote-8)" in result[0]

        # Second sentence should have 2 citations
        assert "[[10]](#footnote-9)" in result[1]
        assert "[[11]](#footnote-10)" in result[1]

    @pytest.mark.asyncio
    async def test_bold_paragraph_with_inline_citations(self):
        """
        Bold paragraphs with inline citations should not split incorrectly.

        Tests markdown bold syntax combined with citations - a common pattern
        in RAND documents for emphasis.
        """
        paragraph = (
            "**The anticipated load growth from AI is unprecedented in both magnitude and speed.** "
            "Developing advanced AI models requires enormous amounts of power[[4]](#footnote-3) "
            "and existing facilities are already straining U.S. electrical grids.[[5]](#footnote-4)"
        )

        result = await split_paragraph_into_sentences(
            paragraph, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        # Should be 2 sentences (bold doesn't create a sentence boundary)
        assert len(result) == 2, f"Expected 2 chunks but got {len(result)}: {result}"

        # First sentence should include the bold markers
        assert "**The anticipated load growth" in result[0]
        assert "speed.**" in result[0]

        # Second sentence should have citations
        assert "[[4]](#footnote-3)" in result[1]
        assert "[[5]](#footnote-4)" in result[1]

    @pytest.mark.asyncio
    async def test_citation_only_fragment_should_not_exist(self):
        """
        Isolated citation markers should never appear as standalone chunks.

        This is a regression test for the bug where chunks like "[[14]](#footnote-13)"
        appear as isolated fragments.
        """
        paragraph = (
            "An individual facility may consume up to 5 GW by 2030,[[12]](#footnote-11) "
            "a substantial scale comparable to the 2023 net summer generation capacity[[13]](#footnote-12) "
            "of a single state such as Idaho (5.4 GW), Maine (5.3 GW), or New Hampshire (4.5 GW).[[14]](#footnote-13)"
        )

        result = await split_paragraph_into_sentences(
            paragraph, sentence_tokenizer=SentenceTokenizerAgent(create_test_context())
        )

        # Should be 1 sentence
        assert len(result) == 1, f"Expected 1 chunk but got {len(result)}: {result}"

        # The sentence should contain all citations
        assert "[[12]](#footnote-11)" in result[0]
        assert "[[13]](#footnote-12)" in result[0]
        assert "[[14]](#footnote-13)" in result[0]

        # Verify the entire sentence is intact
        assert "An individual facility" in result[0]
        assert "New Hampshire (4.5 GW)" in result[0]


if __name__ == "__main__":
    # Run tests to demonstrate failures
    pytest.main([__file__, "-v", "--tb=short"])
