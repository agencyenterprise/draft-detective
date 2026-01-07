"""
Test all fragment detection methods to compare their effectiveness.

This test suite runs the same test cases against all three detection methods:
1. Reconstruction Quality
2. Semantic Coherence (Embeddings)
3. Statistical Anomaly Detection

This allows us to compare accuracy and behavior across methods.
"""

import pytest
from lib.services.fragment_detection import (
    detect_by_reconstruction_quality,
    detect_by_semantic_coherence,
    detect_by_statistical_anomalies,
    has_suspicious_fragments,
)


class TestFragmentDetectionMethods:
    """Test all detection methods with the same test cases."""

    @pytest.mark.asyncio
    async def test_citation_et_al_reconstruction(self):
        """Reconstruction method should detect incorrectly split citation."""
        original = "Johnson et al. (2020). Machine Learning Approaches to Data Analysis. Nature Machine Intelligence, 5(2), 123-145."
        # This is what NLTK produces (incorrectly split)
        nltk_output = [
            "Johnson et al.",
            "(2020).",
            "Machine Learning Approaches to Data Analysis.",
            "Nature Machine Intelligence, 5(2), 123-145.",
        ]

        is_suspicious, score = detect_by_reconstruction_quality(nltk_output, original)
        assert is_suspicious is True, "Should detect suspicious fragments"
        assert score > 0, "Should have a positive suspicion score"

    @pytest.mark.asyncio
    async def test_citation_et_al_semantic(self):
        """Semantic method should detect incorrectly split citation."""
        original = "Johnson et al. (2020). Machine Learning Approaches to Data Analysis. Nature Machine Intelligence, 5(2), 123-145."
        nltk_output = [
            "Johnson et al.",
            "(2020).",
            "Machine Learning Approaches to Data Analysis.",
            "Nature Machine Intelligence, 5(2), 123-145.",
        ]

        is_suspicious, score = await detect_by_semantic_coherence(nltk_output, original)
        assert is_suspicious is True, "Should detect suspicious fragments"
        assert score > 0, "Should have a positive suspicion score"

    @pytest.mark.asyncio
    async def test_citation_et_al_statistical(self):
        """Statistical method should detect incorrectly split citation."""
        original = "Johnson et al. (2020). Machine Learning Approaches to Data Analysis. Nature Machine Intelligence, 5(2), 123-145."
        nltk_output = [
            "Johnson et al.",
            "(2020).",
            "Machine Learning Approaches to Data Analysis.",
            "Nature Machine Intelligence, 5(2), 123-145.",
        ]

        is_suspicious, score = detect_by_statistical_anomalies(nltk_output, original)
        assert is_suspicious is True, "Should detect suspicious fragments"
        assert score > 0, "Should have a positive suspicion score"

    @pytest.mark.asyncio
    async def test_regular_prose_reconstruction(self):
        """Reconstruction: Regular prose should pass."""
        original = "This is the first sentence. This is the second sentence. And here is a third."
        correct_output = [
            "This is the first sentence.",
            "This is the second sentence.",
            "And here is a third.",
        ]

        is_suspicious, score = detect_by_reconstruction_quality(
            correct_output, original
        )
        assert is_suspicious is False, "Should NOT flag correct tokenization"

    @pytest.mark.asyncio
    async def test_regular_prose_semantic(self):
        """Semantic: Regular prose should pass."""
        original = "This is the first sentence. This is the second sentence. And here is a third."
        correct_output = [
            "This is the first sentence.",
            "This is the second sentence.",
            "And here is a third.",
        ]

        is_suspicious, score = await detect_by_semantic_coherence(
            correct_output, original
        )
        assert is_suspicious is False, "Should NOT flag correct tokenization"

    @pytest.mark.asyncio
    async def test_regular_prose_statistical(self):
        """Statistical: Regular prose should pass."""
        original = "This is the first sentence. This is the second sentence. And here is a third."
        correct_output = [
            "This is the first sentence.",
            "This is the second sentence.",
            "And here is a third.",
        ]

        is_suspicious, score = detect_by_statistical_anomalies(correct_output, original)
        assert is_suspicious is False, "Should NOT flag correct tokenization"

    @pytest.mark.asyncio
    async def test_complex_citation_reconstruction(self):
        """Reconstruction: Should detect complex citation splits."""
        original = "Anderson, R. J., Smith, P. K., & Williams, M. T. (2021). Advanced Topics in A.I. Research. Proc. Natl. Acad. Sci. U.S.A., 118(25), e2021234118."
        # Badly split
        bad_split = [
            "Anderson, R. J., Smith, P. K., & Williams, M. T.",
            "(2021).",
            "Advanced Topics in A.I.",
            "Research.",
            "Proc.",
            "Natl.",
            "Acad.",
            "Sci.",
            "U.S.A., 118(25), e2021234118.",
        ]

        is_suspicious, score = detect_by_reconstruction_quality(bad_split, original)
        assert is_suspicious is True, "Should detect complex citation fragmentation"
        assert score > 0, "Should have a positive suspicion score"

    @pytest.mark.asyncio
    async def test_complex_citation_statistical(self):
        """Statistical: Should detect complex citation splits."""
        original = "Anderson, R. J., Smith, P. K., & Williams, M. T. (2021). Advanced Topics in A.I. Research. Proc. Natl. Acad. Sci. U.S.A., 118(25), e2021234118."
        bad_split = [
            "Anderson, R. J., Smith, P. K., & Williams, M. T.",
            "(2021).",
            "Advanced Topics in A.I.",
            "Research.",
            "Proc.",
            "Natl.",
            "Acad.",
            "Sci.",
            "U.S.A., 118(25), e2021234118.",
        ]

        is_suspicious, score = detect_by_statistical_anomalies(bad_split, original)
        assert is_suspicious is True, "Should detect many short fragments"
        assert score > 0, "Should have a positive suspicion score"

    @pytest.mark.asyncio
    async def test_single_sentence_all_methods(self):
        """All methods: Single sentence should never be suspicious."""
        original = "This is a single sentence with no splits."
        single = [original]

        is_suspicious, _ = detect_by_reconstruction_quality(single, original)
        assert is_suspicious is False
        is_suspicious, _ = await detect_by_semantic_coherence(single, original)
        assert is_suspicious is False
        is_suspicious, _ = detect_by_statistical_anomalies(single, original)
        assert is_suspicious is False

    @pytest.mark.asyncio
    async def test_technical_text_reconstruction(self):
        """Reconstruction: Technical text should be handled correctly."""
        original = "The U.S. Navy deployed the new A.I. system in 2023. It improved efficiency by 20%."
        correct_split = [
            "The U.S. Navy deployed the new A.I. system in 2023.",
            "It improved efficiency by 20%.",
        ]

        is_suspicious, score = detect_by_reconstruction_quality(correct_split, original)
        assert is_suspicious is False, "Correct technical text should not be flagged"

    @pytest.mark.asyncio
    async def test_bimodal_distribution_statistical(self):
        """Statistical: Should detect bimodal length distribution."""
        original = "A. This is a much longer sentence that contains substantial content and multiple clauses which makes it significantly different in length."
        bad_split = [
            "A.",  # Very short
            "This is a much longer sentence that contains substantial content and multiple clauses which makes it significantly different in length.",  # Very long
        ]

        is_suspicious, score = detect_by_statistical_anomalies(bad_split, original)
        assert is_suspicious is True, "Should detect bimodal distribution"
        assert score > 0, "Should have a positive suspicion score"

    @pytest.mark.asyncio
    async def test_multiple_single_words_statistical(self):
        """Statistical: Should detect multiple single-word fragments."""
        original = "Dr. Smith met Dr. Jones and Dr. Brown yesterday."
        bad_split = [
            "Dr.",
            "Smith met Dr.",
            "Jones and Dr.",
            "Brown yesterday.",
        ]

        is_suspicious, score = detect_by_statistical_anomalies(bad_split, original)
        # Has multiple very short fragments
        assert is_suspicious is True, "Should detect multiple short fragments"
        assert score > 0, "Should have a positive suspicion score"


class TestConfigurableDetection:
    """Test the main has_suspicious_fragments function with different methods."""

    @pytest.mark.asyncio
    async def test_method_selection_reconstruction(self):
        """Test that method='reconstruction' works."""
        original = "Johnson et al. (2020). Paper Title."
        bad_split = ["Johnson et al.", "(2020).", "Paper Title."]

        is_suspicious, score = await has_suspicious_fragments(
            bad_split, original, method="reconstruction"
        )
        assert is_suspicious is True
        assert score > 0

    @pytest.mark.asyncio
    async def test_method_selection_semantic(self):
        """Test that method='semantic' works."""
        original = "Johnson et al. (2020). Paper Title."
        bad_split = ["Johnson et al.", "(2020).", "Paper Title."]

        is_suspicious, score = await has_suspicious_fragments(
            bad_split, original, method="semantic"
        )
        assert is_suspicious is True
        assert score > 0

    @pytest.mark.asyncio
    async def test_method_selection_statistical(self):
        """Test that method='statistical' works."""
        original = "Johnson et al. (2020). Paper Title."
        bad_split = ["Johnson et al.", "(2020).", "Paper Title."]

        is_suspicious, score = await has_suspicious_fragments(
            bad_split, original, method="statistical"
        )
        assert is_suspicious is True
        assert score > 0

    @pytest.mark.asyncio
    async def test_invalid_method_raises_error(self):
        """Test that invalid method raises ValueError."""
        original = "Johnson et al. (2020). Paper Title."
        bad_split = ["Johnson et al.", "(2020).", "Paper Title."]

        with pytest.raises(ValueError, match="Invalid detection method"):
            await has_suspicious_fragments(bad_split, original, method="invalid")

    @pytest.mark.asyncio
    async def test_default_method(self):
        """Test that default method (reconstruction) works."""
        original = "Johnson et al. (2020). Paper Title."
        bad_split = ["Johnson et al.", "(2020).", "Paper Title."]

        # No method specified, should use default
        is_suspicious, score = await has_suspicious_fragments(bad_split, original)
        assert is_suspicious is True
        assert score > 0


class TestEdgeCases:
    """Test edge cases that all methods should handle."""

    @pytest.mark.asyncio
    async def test_empty_list(self):
        """All methods should handle empty list gracefully."""
        is_suspicious, _ = detect_by_reconstruction_quality([], "")
        assert is_suspicious is False
        is_suspicious, _ = await detect_by_semantic_coherence([], "")
        assert is_suspicious is False
        is_suspicious, _ = detect_by_statistical_anomalies([], "")
        assert is_suspicious is False

    @pytest.mark.asyncio
    async def test_single_empty_string(self):
        """All methods should handle list with empty string."""
        is_suspicious, _ = detect_by_reconstruction_quality([""], "")
        assert is_suspicious is False
        is_suspicious, _ = await detect_by_semantic_coherence([""], "")
        assert is_suspicious is False
        is_suspicious, _ = detect_by_statistical_anomalies([""], "")
        assert is_suspicious is False

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        """All methods should handle whitespace-only fragments."""
        fragments = ["  ", "   ", "    "]
        is_suspicious, _ = detect_by_reconstruction_quality(fragments, "   ")
        assert is_suspicious is False
        is_suspicious, _ = await detect_by_semantic_coherence(fragments, "   ")
        assert is_suspicious is False
        is_suspicious, _ = detect_by_statistical_anomalies(fragments, "   ")
        assert is_suspicious is False


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
