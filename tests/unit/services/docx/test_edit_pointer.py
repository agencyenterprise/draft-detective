"""Tests for how a comment points at an edit's changed words."""

from lib.services.docx.comment_markup import plain_text as plain_text_of
from lib.services.docx.edit_pointer import edit_fix, edit_pointer


def test_a_one_word_change_is_quoted_on_both_sides():
    assert (
        edit_pointer(
            "or a service build on the data.", "or a service built on the data."
        )
        == "“build” → “built”"
    )


def test_two_small_changes_are_both_named():
    assert (
        edit_pointer(
            "In total, the confirmation had an estimated total cost of $13 billion.",
            "The confirmation had an estimated cost of $13 billion.",
        )
        == "“In total, the” → “The”; deletes “total”"
    )


def test_a_sentence_turned_around_reads_as_a_rewrite():
    assert (
        edit_pointer(
            "A summary of the competitive environment is shown in Figure 5.",
            "Figure 5 shows a summary of the competitive environment.",
        )
        == "rewrites “A summary of the competitive …”"
    )


def test_a_deletion_and_an_insertion_say_so():
    sentence = "The rate fell as of 2019 in the third quarter of the year."
    assert (
        edit_pointer(sentence, "The rate fell in the third quarter of the year.")
        == "deletes “as of 2019”"
    )
    assert (
        edit_pointer(
            sentence,
            "The annual rate fell as of 2019 in the third quarter of the year.",
        )
        == "adds “annual”"
    )


def test_a_rewrite_names_the_start_of_the_sentence():
    original = (
        "The creation of CERN was driven by the alignment of two sets of interests."
    )
    replacement = "The alignment of two sets of interests drove the creation of CERN."

    assert (
        edit_pointer(original, replacement) == "rewrites “The creation of CERN was …”"
    )


def test_a_long_deletion_says_it_deletes():
    assert (
        edit_pointer("This sentence restates what the previous one already said.", "")
        == "deletes “This sentence restates what the …”"
    )


def test_a_markup_only_change_says_it_reformats():
    assert (
        edit_pointer(
            "The cost rose **sharply** in the third quarter.",
            "The cost rose sharply in the third quarter.",
        )
        == "reformats “The cost rose sharply in …”"
    )


def test_document_marks_are_left_out_of_quotes():
    assert (
        edit_pointer("an *acronym* here[[3]](#footnote-4)", "an *initialism* here")
        == "“acronym” → “initialism”"
    )


def test_the_whole_fix_reads_as_an_instruction():
    assert edit_fix("for 2019", "") == "Delete “for 2019”"
    assert edit_fix("14% rise", "18% rise") == "Replace “14% rise” with “18% rise”"


def test_a_formatting_only_fix_keeps_its_formatting():
    assert edit_fix("rose sharply", "rose **sharply**") == (
        "Replace “rose sharply” with “rose **sharply**”"
    )


def test_a_change_of_emphasis_kind_is_still_visible():
    assert (
        edit_fix("the **term**", "the *term*")
        == "Replace “the **term**” with “the *term*”"
    )


def test_deleting_a_footnote_link_names_the_footnote():
    assert edit_fix("[[1]](#footnote-2)", "") == "Delete “[1]”"


def test_a_footnote_change_beside_a_word_change_is_kept():
    assert edit_fix("old[[1]](#footnote-1)", "new[[2]](#footnote-2)") == (
        "Replace “old[1]” with “new[2]”"
    )


def test_a_full_fix_keeps_code_as_written():
    assert edit_fix("Use `a**b**c` here", "Use `a**b**c` there") == (
        "Replace “Use `a**b**c` here” with “Use `a**b**c` there”"
    )


def test_literal_asterisks_in_a_pointer_stay_literal():
    pointer = edit_pointer(
        "The rate fell as the `a*b` term grew this quarter.",
        "The rate fell as the `a*b` term rose this quarter.",
    )
    assert pointer == "“grew” → “rose”"
    deleted = edit_pointer(
        "Five a*b times in the third quarter of the year.",
        "Five times in the third quarter of the year.",
    )
    assert deleted == "deletes “a\\*b”"


def test_a_full_fix_keeps_formatting_beside_a_word_change():
    assert edit_fix("a *bad* term", "a **good** term") == (
        "Replace “a *bad* term” with “a **good** term”"
    )


def test_a_changed_link_destination_is_visible_in_the_fix():
    assert plain_text_of(
        edit_fix("[Report](https://x/a)", "[Report](https://x/b)")
    ) == ("Replace “Report (https://x/a)” with “Report (https://x/b)”")


def test_a_fragment_of_markup_is_quoted_as_the_document_shows_it():
    # "a*b*c" cut from inside the code span `a*b*c`: parsed alone it would read
    # "abc" with an italic "b", so each side is quoted as the document shows it.
    fix = edit_fix("a*b*c", "x*y*z", "a*b*c", "x*y*z")
    assert plain_text_of(fix) == "Replace “a*b*c” with “x*y*z”"


def test_a_whole_link_keeps_its_destination_with_display_text():
    # display_text holds only the rendered label; the destination must survive.
    fix = edit_fix("[Report](https://x/a)", "[Report](https://x/b)", "Report", "Report")
    assert plain_text_of(fix) == (
        "Replace “Report (https://x/a)” with “Report (https://x/b)”"
    )


def test_a_link_target_with_markup_characters_is_kept():
    fix = edit_fix(
        "[Report](https://x/report_old.pdf)",
        "[Report](https://x/report_new.pdf)",
        "Report",
        "Report",
    )
    assert plain_text_of(fix) == (
        "Replace “Report (https://x/report_old.pdf)” with "
        "“Report (https://x/report_new.pdf)”"
    )
