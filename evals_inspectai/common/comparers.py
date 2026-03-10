from typing import Any

from deepdiff import DeepDiff
from inspect_ai.scorer import Score


def deep_diff_score(
    t1: Any,
    t2: Any,
    match_message: str = "All items match",
) -> Score:
    """Compare two structures using DeepDiff and return an Inspect AI Score.

    Runs DeepDiff with ``ignore_order=True`` and ``get_deep_distance=True``.
    The score value is ``1 - deep_distance``, where *deep_distance* is
    DeepDiff's normalized [0, 1] structural similarity metric.

    Args:
        t1: Expected (target) data.
        t2: Actual (predicted) data.
        match_message: Explanation text used when both structures are equal.

    Returns:
        A ``Score`` with a float value in [0, 1] and a human-readable
        explanation of any differences.
    """

    diff = DeepDiff(t1, t2, verbose_level=2, get_deep_distance=True, ignore_order=True)
    diff_for_display = DeepDiff(t1, t2, verbose_level=2, ignore_order=True)

    value = 1.0 - float(diff.get("deep_distance", 0.0))
    explanation = diff_for_display.pretty() if diff_for_display else match_message
    return Score(value=value, explanation=explanation)
