"""Parser for simplified field selection syntax."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .errors import ParseError


@dataclass
class FieldSelection:
    """Represents a parsed field selection."""

    fields: set[str]
    relationships: dict[str, FieldSelection]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FieldSelection):
            return False
        return self.fields == other.fields and self.relationships == other.relationships


def parse_query_string(query_string: str) -> FieldSelection:
    """
    Parse a simplified field selection syntax.

    Args:
        query_string: Field selection like "{ id name posts { title } }"

    Returns:
        FieldSelection with fields and nested relationships

    Raises:
        ParseError: If the syntax is invalid
    """
    tokens = _tokenize(query_string)
    if not tokens:
        raise ParseError("Empty query string")

    result, _ = _parse_selection(tokens, 0)
    return result


def _tokenize(query_string: str) -> list[str]:
    """Tokenize the query string into meaningful tokens."""
    # Match braces, identifiers, and skip whitespace/commas
    pattern = r'(\{|\}|[a-zA-Z_][a-zA-Z0-9_]*)'
    tokens = re.findall(pattern, query_string)
    return tokens


def _parse_selection(tokens: list[str], index: int) -> tuple[FieldSelection, int]:
    """
    Parse a selection set starting at the given index.

    Returns:
        Tuple of (FieldSelection, next_index)
    """
    if index >= len(tokens) or tokens[index] != '{':
        raise ParseError(f"Expected '{{' at position {index}")

    index += 1  # Skip opening brace

    fields: set[str] = set()
    relationships: dict[str, FieldSelection] = {}

    while index < len(tokens) and tokens[index] != '}':
        token = tokens[index]

        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', token):
            raise ParseError(f"Invalid token '{token}' at position {index}")

        # Look ahead to see if this is a relationship (followed by {)
        if index + 1 < len(tokens) and tokens[index + 1] == '{':
            # It's a relationship
            nested_selection, index = _parse_selection(tokens, index + 1)
            relationships[token] = nested_selection
        else:
            # It's a field
            fields.add(token)
            index += 1

    if index >= len(tokens):
        raise ParseError("Missing closing brace '}'")

    # index is now at the closing brace
    index += 1  # Skip closing brace

    if not fields and not relationships:
        raise ParseError("Empty selection set")

    return FieldSelection(fields=fields, relationships=relationships), index


@lru_cache(maxsize=256)
def parse_query_string_cached(query_string: str) -> FieldSelection:
    """
    Parse and cache the result. Queries are often repeated.

    This is a cached wrapper around parse_query_string for better performance
    when the same query strings are used multiple times.

    Args:
        query_string: Field selection like "{ id name posts { title } }"

    Returns:
        FieldSelection with fields and nested relationships
    """
    return parse_query_string(query_string)
