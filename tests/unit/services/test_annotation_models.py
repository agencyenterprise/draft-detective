"""Unit tests for the annotation request models."""

import pytest
from pydantic import ValidationError

from lib.services.annotations.models import MAX_TIME_SPENT_MS, AnnotationSubmission


def _submission(time_spent_ms: int | None) -> AnnotationSubmission:
    return AnnotationSubmission(
        answers={"should_flag": "yes"}, time_spent_ms=time_spent_ms
    )


def test_time_spent_beyond_the_integer_column_is_capped():
    assert _submission(10**12).time_spent_ms == MAX_TIME_SPENT_MS


@pytest.mark.parametrize("value", [None, 0, 1234, MAX_TIME_SPENT_MS])
def test_time_spent_within_range_is_kept(value):
    assert _submission(value).time_spent_ms == value


def test_negative_time_spent_is_rejected():
    with pytest.raises(ValidationError):
        _submission(-1)
