"""Tests for the simplified syntax parser."""

import pytest

from sqlalchemy_query_load_generator.parser import FieldSelection, parse_query_string
from sqlalchemy_query_load_generator.errors import ParseError


class TestParseQueryString:
    """Tests for parse_query_string function."""

    def test_simple_fields(self):
        """Parse simple field selection without nested relationships."""
        result = parse_query_string("{ id name email }")

        assert result == FieldSelection(
            fields={"id", "name", "email"},
            relationships={}
        )

    def test_single_field(self):
        """Parse single field selection."""
        result = parse_query_string("{ id }")

        assert result == FieldSelection(
            fields={"id"},
            relationships={}
        )

    def test_fields_without_spaces_around_braces(self):
        """Parse fields without spaces around braces."""
        result = parse_query_string("{id name email}")

        assert result == FieldSelection(
            fields={"id", "name", "email"},
            relationships={}
        )

    def test_fields_with_extra_whitespace(self):
        """Parse fields with extra whitespace and newlines."""
        query = """
        {
            id
            name
            email
        }
        """
        result = parse_query_string(query)

        assert result == FieldSelection(
            fields={"id", "name", "email"},
            relationships={}
        )

    def test_fields_with_optional_commas(self):
        """Parse fields with optional comma separators."""
        result = parse_query_string("{ id, name, email }")

        assert result == FieldSelection(
            fields={"id", "name", "email"},
            relationships={}
        )

    def test_nested_relationship(self):
        """Parse nested relationship selection."""
        result = parse_query_string("{ id posts { title } }")

        assert result == FieldSelection(
            fields={"id"},
            relationships={
                "posts": FieldSelection(
                    fields={"title"},
                    relationships={}
                )
            }
        )

    def test_deeply_nested_relationships(self):
        """Parse deeply nested relationship selections."""
        result = parse_query_string("{ id posts { title comments { content } } }")

        assert result == FieldSelection(
            fields={"id"},
            relationships={
                "posts": FieldSelection(
                    fields={"title"},
                    relationships={
                        "comments": FieldSelection(
                            fields={"content"},
                            relationships={}
                        )
                    }
                )
            }
        )

    def test_multiple_relationships(self):
        """Parse multiple relationships at the same level."""
        result = parse_query_string("{ id posts { title } comments { content } }")

        assert result == FieldSelection(
            fields={"id"},
            relationships={
                "posts": FieldSelection(fields={"title"}, relationships={}),
                "comments": FieldSelection(fields={"content"}, relationships={})
            }
        )

    def test_mixed_fields_and_relationships(self):
        """Parse mix of scalar fields and relationships."""
        result = parse_query_string("{ id name posts { id title } profile { bio } }")

        assert result == FieldSelection(
            fields={"id", "name"},
            relationships={
                "posts": FieldSelection(fields={"id", "title"}, relationships={}),
                "profile": FieldSelection(fields={"bio"}, relationships={})
            }
        )

    def test_empty_selection_raises_error(self):
        """Empty selection should raise ParseError."""
        with pytest.raises(ParseError):
            parse_query_string("{}")

    def test_missing_closing_brace_raises_error(self):
        """Missing closing brace should raise ParseError."""
        with pytest.raises(ParseError):
            parse_query_string("{ id name")

    def test_missing_opening_brace_raises_error(self):
        """Missing opening brace should raise ParseError."""
        with pytest.raises(ParseError):
            parse_query_string("id name }")

    def test_unmatched_braces_raises_error(self):
        """Unmatched braces should raise ParseError."""
        with pytest.raises(ParseError):
            parse_query_string("{ id { name }")

    def test_empty_nested_selection_raises_error(self):
        """Empty nested selection should raise ParseError."""
        with pytest.raises(ParseError):
            parse_query_string("{ posts {} }")


class TestFieldSelection:
    """Tests for FieldSelection dataclass."""

    def test_empty_selection(self):
        """Create empty field selection."""
        selection = FieldSelection(fields=set(), relationships={})

        assert selection.fields == set()
        assert selection.relationships == {}

    def test_selection_equality(self):
        """Field selections should compare equal."""
        sel1 = FieldSelection(fields={"id", "name"}, relationships={})
        sel2 = FieldSelection(fields={"name", "id"}, relationships={})

        assert sel1 == sel2
