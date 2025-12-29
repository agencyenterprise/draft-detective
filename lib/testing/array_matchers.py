"""Array matching strategies for intelligent item-to-item comparison."""

from difflib import SequenceMatcher
from typing import Any


class ArrayMatcher:
    """Provides multiple strategies for matching array items intelligently.

    Strategies:
        1. by_field: Match items by primary field value (semantic)
        2. by_index: Match items positionally when counts align (structural)
        3. best_effort: Fuzzy matching with similarity threshold (robust)
    """

    def __init__(self, fuzzy_threshold: float = 0.6, good_match_threshold: float = 0.8):
        """Initialize array matcher with configurable thresholds.

        Args:
            fuzzy_threshold: Minimum similarity score for fuzzy matches (0.0-1.0)
            good_match_threshold: Minimum ratio of matched items to consider strategy successful
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.good_match_threshold = good_match_threshold

    def match_items(
        self,
        expected_items: list[dict],
        result_items: list[dict],
        field_names: list[str],
    ) -> tuple[list[tuple[dict | None, dict | None, str]], str]:
        """Match array items using multiple fallback strategies.

        Args:
            expected_items: List of expected items as dicts
            result_items: List of actual items as dicts
            field_names: List of field names to use for matching

        Returns:
            Tuple of (matches, strategy_name) where matches is a list of
            (expected_item, actual_item, match_id) tuples
        """
        if len(expected_items) == 0 and len(result_items) == 0:
            return [], "empty"

        # Strategy 1: Match by first field (usually 'text' or similar)
        if field_names:
            primary_field = field_names[0]
            matches = self._match_by_field(expected_items, result_items, primary_field)
            if self._is_good_match(matches):
                return matches, f"by_{primary_field}"

        # Strategy 2: Match by index (if counts match)
        if len(expected_items) == len(result_items):
            matches = [
                (exp, res, f"index_{i}")
                for i, (exp, res) in enumerate(
                    zip(expected_items, result_items, strict=True)
                )
            ]
            return matches, "by_index"

        # Strategy 3: Best effort with fuzzy matching
        matches = self._match_best_effort(expected_items, result_items, field_names)
        return matches, "best_effort"

    def _match_by_field(
        self, expected_items: list[dict], result_items: list[dict], match_field: str
    ) -> list[tuple[dict | None, dict | None, str]]:
        """Match items by a specific field value.

        Args:
            expected_items: Expected items
            result_items: Actual items
            match_field: Field name to use for matching

        Returns:
            List of (expected, actual, match_id) tuples
        """
        matches = []
        result_copy = list(result_items)

        for i, exp_item in enumerate(expected_items):
            exp_val = exp_item.get(match_field)
            matched_item = None
            match_id = f"exp[{i}]"

            # Find matching result
            for j, res_item in enumerate(result_copy):
                res_val = res_item.get(match_field)
                if self._values_match(exp_val, res_val):
                    matched_item = result_copy.pop(j)
                    match_id = f"{match_field}={exp_val}"
                    break

            matches.append((exp_item, matched_item, match_id))

        # Add unmatched result items
        for j, res_item in enumerate(result_copy):
            res_val = res_item.get(match_field)
            match_id = f"extra_{match_field}={res_val}"
            matches.append((None, res_item, match_id))

        return matches

    def _match_best_effort(
        self,
        expected_items: list[dict],
        result_items: list[dict],
        field_names: list[str],
    ) -> list[tuple[dict | None, dict | None, str]]:
        """Best effort matching with fuzzy similarity.

        Uses SequenceMatcher to find best matches based on field similarity.

        Args:
            expected_items: Expected items
            result_items: Actual items
            field_names: Fields to use for similarity calculation

        Returns:
            List of (expected, actual, match_id) tuples
        """
        matches = []
        result_copy = list(result_items)

        for i, exp_item in enumerate(expected_items):
            best_match = None
            best_score = 0.0
            best_idx = -1

            # Try to find best matching item
            for j, res_item in enumerate(result_copy):
                score = self._similarity_score(exp_item, res_item, field_names)
                if score > best_score:
                    best_score = score
                    best_match = res_item
                    best_idx = j

            # Use match if similarity > threshold
            if best_score > self.fuzzy_threshold and best_match:
                result_copy.pop(best_idx)
                matches.append(
                    (exp_item, best_match, f"fuzzy[{i}]_score={best_score:.2f}")
                )
            else:
                matches.append((exp_item, None, f"missing_exp[{i}]"))

        # Add remaining unmatched
        for j, res_item in enumerate(result_copy):
            matches.append((None, res_item, f"extra_actual[{j}]"))

        return matches

    def _similarity_score(
        self, item1: dict, item2: dict, field_names: list[str]
    ) -> float:
        """Calculate similarity between two items based on their fields.

        Args:
            item1: First item
            item2: Second item
            field_names: Fields to compare

        Returns:
            Similarity score between 0.0 and 1.0
        """
        scores = []
        for field in field_names:
            val1 = str(item1.get(field, ""))
            val2 = str(item2.get(field, ""))
            if val1 and val2:
                score = SequenceMatcher(None, val1, val2).ratio()
                scores.append(score)

        return sum(scores) / len(scores) if scores else 0.0

    def _is_good_match(self, matches: list) -> bool:
        """Check if matching strategy produced good results.

        Args:
            matches: List of match tuples

        Returns:
            True if at least good_match_threshold of items have both expected and actual
        """
        if not matches:
            return False

        both_present = sum(1 for exp, res, _ in matches if exp and res)
        return both_present / len(matches) >= self.good_match_threshold

    @staticmethod
    def _values_match(val1: Any, val2: Any) -> bool:
        """Check if two values match with tolerance.

        Args:
            val1: First value
            val2: Second value

        Returns:
            True if values are considered equal
        """
        if val1 == val2:
            return True

        # Handle None vs empty string
        if val1 in (None, "") and val2 in (None, ""):
            return True

        # Handle numeric comparisons with tolerance
        if isinstance(val1, int | float) and isinstance(val2, int | float):
            return abs(val1 - val2) < 1e-9

        return False
