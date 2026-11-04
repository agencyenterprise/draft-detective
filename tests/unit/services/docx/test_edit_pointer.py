"""Tests for how a comment points at an edit's changed words."""

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
