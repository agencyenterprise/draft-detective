"""Tests for PostgreSQL sanitization utilities"""

import pytest

from lib.services.text_sanitization import sanitize_for_postgres


class TestSanitizeForPostgres:
    """Tests for the sanitize_for_postgres function"""

    def test_removes_null_character_from_string(self):
        input_str = "Hello\u0000World"
        result = sanitize_for_postgres(input_str)
        assert result == "HelloWorld"
        assert "\u0000" not in result

    def test_removes_multiple_null_characters(self):
        input_str = "Start\u0000Middle\u0000End\u0000"
        result = sanitize_for_postgres(input_str)
        assert result == "StartMiddleEnd"

    def test_handles_string_without_null_characters(self):
        input_str = "Normal string without issues"
        result = sanitize_for_postgres(input_str)
        assert result == input_str

    def test_handles_empty_string(self):
        result = sanitize_for_postgres("")
        assert result == ""

    def test_sanitizes_dict_string_values(self):
        input_dict = {
            "title": "Document\u0000Title",
            "summary": "Some\u0000summary\u0000text",
        }
        result = sanitize_for_postgres(input_dict)
        assert result["title"] == "DocumentTitle"
        assert result["summary"] == "Somesummarytext"

    def test_sanitizes_nested_dict(self):
        input_dict = {
            "outer": {
                "inner": "Nested\u0000value",
                "deep": {
                    "value": "Deep\u0000nested",
                },
            },
        }
        result = sanitize_for_postgres(input_dict)
        assert result["outer"]["inner"] == "Nestedvalue"
        assert result["outer"]["deep"]["value"] == "Deepnested"

    def test_sanitizes_list_of_strings(self):
        input_list = ["First\u0000item", "Second\u0000item", "Clean item"]
        result = sanitize_for_postgres(input_list)
        assert result == ["Firstitem", "Seconditem", "Clean item"]

    def test_sanitizes_list_of_dicts(self):
        input_list = [
            {"name": "Item\u0000One"},
            {"name": "Item\u0000Two"},
        ]
        result = sanitize_for_postgres(input_list)
        assert result[0]["name"] == "ItemOne"
        assert result[1]["name"] == "ItemTwo"

    def test_sanitizes_mixed_nested_structure(self):
        input_data = {
            "title": "Doc\u0000Title",
            "authors": ["Author\u0000One", "Author Two"],
            "metadata": {
                "abstract": "Abstract\u0000text",
                "keywords": ["key\u0000word1", "keyword2"],
            },
        }
        result = sanitize_for_postgres(input_data)
        assert result["title"] == "DocTitle"
        assert result["authors"] == ["AuthorOne", "Author Two"]
        assert result["metadata"]["abstract"] == "Abstracttext"
        assert result["metadata"]["keywords"] == ["keyword1", "keyword2"]

    def test_preserves_non_string_values(self):
        input_dict = {
            "count": 42,
            "price": 19.99,
            "active": True,
            "data": None,
        }
        result = sanitize_for_postgres(input_dict)
        assert result["count"] == 42
        assert result["price"] == 19.99
        assert result["active"] is True
        assert result["data"] is None

    def test_handles_none_value(self):
        result = sanitize_for_postgres(None)
        assert result is None

    def test_handles_integer_value(self):
        result = sanitize_for_postgres(123)
        assert result == 123

    def test_handles_float_value(self):
        result = sanitize_for_postgres(3.14)
        assert result == 3.14

    def test_handles_boolean_value(self):
        assert sanitize_for_postgres(True) is True
        assert sanitize_for_postgres(False) is False

    def test_handles_empty_dict(self):
        result = sanitize_for_postgres({})
        assert result == {}

    def test_handles_empty_list(self):
        result = sanitize_for_postgres([])
        assert result == []

    def test_real_world_llm_output_example(self):
        """Test with a realistic example similar to the actual error"""
        input_data = {
            "title": "F-15EX Planned Fleet Size Grows To 129 Jets",
            "authors": "",
            "publication_date": "2025-06-26",
            "abstract": "Unknown",
            "summary": "This is a change in the United States Air Force\u0000 fleet "
            "composition that reflects strategic priorities.",
        }
        result = sanitize_for_postgres(input_data)
        assert "\u0000" not in result["summary"]
        assert "United States Air Force fleet" in result["summary"]
