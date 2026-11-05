"""Tests for the passage each abbreviation occurrence's issue is anchored on."""

from lib.workflows.abbreviation_scan_v2.issues import build_issues
from lib.workflows.abbreviation_scan_v2.passages import (
    occurrence_passage,
    with_passages,
)
from lib.workflows.abbreviation_scan_v2.state import (
    AbbreviationItem,
    AbbreviationScanV2Config,
    AbbreviationScanV2State,
)

_LINES = [
    "The GAO reviewed the program.",  # 1
    "DoD guidance and later DoD policy differ.",  # 2
    "The Office of the Under Secretary of War (OUSW) leads it.",  # 3
    "The U.S. budget grew.",  # 4
    "The **NATO** summit met.",  # 5
    "AI is used in OpenAI products and in MAIN AI systems.",  # 6
    "The Lab (CAIRNE) which funds CAIRNE fellows.",  # 7
    "Once CLAIRE, now CAIRNE) and CAIRNE, again.",  # 8
]


def _item(abbr: str, line: int, definition: str = "") -> AbbreviationItem:
    return AbbreviationItem(
        abbr=abbr,
        inline_definition=definition,
        occurrence_number=1,
        line_start=line,
        line_end=line,
    )


def _text(item: AbbreviationItem, nth: int = 0) -> str | None:
    passage = occurrence_passage(_LINES, item, nth)
    return passage.display_text if passage else None


def test_a_unique_abbreviation_is_its_own_passage():
    passage = occurrence_passage(_LINES, _item("GAO", 1), 0)

    assert passage is not None
    assert passage.display_text == "GAO"
    assert (passage.start_line, passage.end_line) == (1, 1)


def test_a_repeated_abbreviation_is_widened_until_it_is_unique():
    # Each DoD gains the word before it, or after it when it opens the line.
    assert _text(_item("DoD", 2), 0) == "DoD guidance"
    assert _text(_item("DoD", 2), 1) == "later DoD"


def test_an_inline_definition_is_quoted_with_its_abbreviation():
    assert (
        _text(_item("OUSW", 3, "Office of the Under Secretary of War"))
        == "Office of the Under Secretary of War (OUSW)"
    )


def test_the_spelling_the_line_carries_is_quoted():
    assert _text(_item("US", 4)) == "U.S."


def test_markup_around_the_abbreviation_is_rendered_away():
    assert _text(_item("NATO", 5)) == "NATO"


def test_a_token_inside_a_longer_word_is_not_counted_or_chosen():
    # "OpenAI" and "MAIN" hold "AI" but not as a token; the first token is
    # still repeated, so it is widened past the second's neighbourhood.
    assert _text(_item("AI", 6), 0) == "AI is"


def test_an_occurrence_nothing_pins_down_has_no_passage():
    assert occurrence_passage(_LINES, _item("XYZ", 1), 0) is None
    assert occurrence_passage(_LINES, _item("GAO", 99), 0) is None


def test_the_catalogue_counts_repeats_per_line_and_issues_carry_the_passage():
    catalogue = with_passages(
        _LINES, [_item("DoD", 2), _item("DoD", 2), _item("GAO", 1)]
    )

    assert [i.passage.display_text if i.passage else None for i in catalogue] == [
        "DoD guidance",
        "later DoD",
        "GAO",
    ]
    state = AbbreviationScanV2State(
        config=AbbreviationScanV2Config(project_id="p"),
        abbreviations=[catalogue[0], catalogue[2]],
    )
    issues = build_issues(state)
    assert {i.passage.display_text for i in issues if i.passage} == {
        "DoD guidance",
        "GAO",
    }


def test_widening_takes_the_whole_word_around_the_token_first():
    # "CAIRNE" repeats; the first grows to "(CAIRNE)", never to "CAIRNE) which".
    assert _text(_item("CAIRNE", 7), 0) == "(CAIRNE)"


def test_the_word_before_is_taken_first():
    line = "(CLAIRE, later renamed CAIRNE) which was created in 2018; CAIRNE grew."
    item = AbbreviationItem(
        abbr="CAIRNE",
        inline_definition="",
        occurrence_number=1,
        line_start=1,
        line_end=1,
    )
    passage = occurrence_passage([line], item, 0)
    assert passage is not None and passage.display_text == "renamed CAIRNE"


def test_whole_word_widening_sheds_punctuation_it_does_not_close():
    assert _text(_item("CAIRNE", 8), 0) == "now CAIRNE"


def test_exempt_url_token_does_not_shift_the_recorded_occurrence():
    """Review probe (DUDU-17): the skill leaves URL occurrences out of the
    catalogue, so the only recorded CAST on this line is the prose one. Which
    token it is cannot be told by order, so it is not guessed: the issue keeps
    its whole line rather than highlight the link."""
    lines = ["See [www.rand.org/CAST](http://www.rand.org/CAST) for the CAST results."]
    [item] = with_passages(lines, [_item("CAST", 1)])
    assert item.passage is None


def test_a_definition_still_places_an_occurrence_whose_token_is_unknown():
    lines = [
        "See [the CAST page](http://x.org/CAST) on the Cost Analysis Study Tool (CAST)."
    ]
    [item] = with_passages(lines, [_item("CAST", 1, "Cost Analysis Study Tool")])
    assert item.passage is not None
    assert item.passage.display_text == "Cost Analysis Study Tool (CAST)"


def test_an_entity_spelled_token_is_not_mistaken_for_the_next_one():
    """The catalogue counts tokens after decoding entities, so it sees two R&D
    here; the raw line matches one. The first recorded R&D is not guessed onto
    the second, which is the one the raw line carries."""
    lines = ["The R&amp;D team compared R & D budgets."]
    first, _ = with_passages(lines, [_item("R&D", 1), _item("R&D", 1)])
    assert first.passage is None
