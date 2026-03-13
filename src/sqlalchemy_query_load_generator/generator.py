"""LoadGenerator core class."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import class_mapper, load_only, selectinload

from .errors import FieldNotFoundError, RelationshipNotFoundError
from .parser import FieldSelection, parse_query_string


class LoadGenerator:
    """
    Generate SQLAlchemy query optimization options from simplified field selection syntax.

    Example:
        generator = LoadGenerator(User)
        options = generator.generate("{ id name posts { title } }")
        stmt = select(User).options(*options)
    """

    def __init__(self, model_class: type):
        """
        Initialize LoadGenerator with a SQLAlchemy model class.

        Args:
            model_class: SQLAlchemy declarative model class

        Raises:
            TypeError: If model_class is not a valid SQLAlchemy model
        """
        self.model_class = model_class
        self._relationship_names = self._detect_relationships()
        self._column_names = self._detect_columns()

    def _detect_relationships(self) -> set[str]:
        """Detect all relationship attribute names from the model."""
        try:
            mapper = class_mapper(self.model_class)
            return {rel.key for rel in mapper.relationships}
        except Exception:
            return set()

    def _detect_columns(self) -> set[str]:
        """Detect all column attribute names from the model."""
        try:
            mapper = class_mapper(self.model_class)
            return {col.key for col in mapper.columns}
        except Exception:
            return set()

    def generate(self, query_string: str) -> list[Any]:
        """
        Generate SQLAlchemy query options from field selection string.

        Args:
            query_string: Simplified field selection syntax, e.g. "{ id name posts { title } }"

        Returns:
            List of SQLAlchemy options that can be passed to .options(*options)

        Raises:
            ParseError: If the query string syntax is invalid
            FieldNotFoundError: If a specified field doesn't exist
            RelationshipNotFoundError: If a specified relationship doesn't exist
        """
        selection = parse_query_string(query_string)
        return self._build_options(self.model_class, selection)

    def _build_options(self, model_class: type, selection: FieldSelection) -> list[Any]:
        """
        Recursively build SQLAlchemy options from a FieldSelection.

        Args:
            model_class: The SQLAlchemy model class for this level
            selection: Parsed field selection

        Returns:
            List of SQLAlchemy options
        """
        options = []

        # Get model metadata
        try:
            mapper = class_mapper(model_class)
            column_names = {col.key for col in mapper.columns}
            relationship_names = {rel.key for rel in mapper.relationships}
        except Exception as e:
            raise TypeError(f"Invalid SQLAlchemy model: {model_class}") from e

        # Validate and separate fields from relationships
        valid_fields = set()
        for field_name in selection.fields:
            if field_name in relationship_names:
                # User forgot to add braces for relationship
                raise RelationshipNotFoundError(
                    f"'{field_name}' is a relationship, use '{field_name} {{ ... }}' syntax"
                )
            if field_name not in column_names:
                raise FieldNotFoundError(
                    f"Field '{field_name}' does not exist on {model_class.__name__}"
                )
            valid_fields.add(field_name)

        # Validate relationships
        for rel_name in selection.relationships:
            if rel_name not in relationship_names:
                if rel_name in column_names:
                    raise FieldNotFoundError(
                        f"'{rel_name}' is a column, not a relationship"
                    )
                raise RelationshipNotFoundError(
                    f"Relationship '{rel_name}' does not exist on {model_class.__name__}"
                )

        # 1. Build load_only for scalar fields (with primary key)
        if valid_fields:
            columns = self._ensure_primary_key(model_class, valid_fields)
            options.append(load_only(*columns))

        # 2. Build selectinload for relationships (recursive)
        for rel_name, nested_selection in selection.relationships.items():
            rel_attr = getattr(model_class, rel_name)
            target_model = rel_attr.property.mapper.class_

            nested_options = self._build_options(target_model, nested_selection)
            loader = selectinload(rel_attr).options(*nested_options)
            options.append(loader)

        return options

    def _ensure_primary_key(self, model_class: type, field_names: set[str]) -> list[Any]:
        """
        Ensure primary key columns are included in load_only.

        SQLAlchemy needs primary keys to properly construct objects.

        Args:
            model_class: SQLAlchemy model class
            field_names: Set of field names to load

        Returns:
            List of column attributes for load_only
        """
        mapper = class_mapper(model_class)

        # Get primary key column names
        pk_names = {pk.key for pk in mapper.primary_key}

        # Start with primary keys
        columns = []
        for pk_name in sorted(pk_names):
            columns.append(getattr(model_class, pk_name))

        # Add other requested fields
        for field_name in sorted(field_names):
            if field_name not in pk_names:
                columns.append(getattr(model_class, field_name))

        return columns
