"""LoadGenerator core class."""

from __future__ import annotations

from typing import Any, Type

from sqlalchemy.orm import DeclarativeBase, load_only, selectinload

from .cache import ModelMetadata
from .errors import FieldNotFoundError, RelationshipNotFoundError
from .parser import FieldSelection, parse_query_string_cached


class LoadGenerator:
    """
    Generate SQLAlchemy query optimization options from simplified field selection syntax.

    Example:
        generator = LoadGenerator(Base)  # Pass DeclarativeBase
        options = generator.generate(User, "{ id name posts { title } }")
        stmt = select(User).options(*options)
    """

    def __init__(self, base_class: type[DeclarativeBase]):
        """
        Initialize LoadGenerator with a SQLAlchemy DeclarativeBase.

        Preloads metadata for all models in the registry for better performance.

        Args:
            base_class: SQLAlchemy DeclarativeBase class

        Raises:
            TypeError: If base_class is not a valid DeclarativeBase
        """
        self._base_class = base_class
        self._metadata_cache: dict[type, ModelMetadata] = {}
        self._options_cache: dict[str, list[Any]] = {}
        self._preload_all_metadata()

    def _is_declarative_base(self, cls: type) -> bool:
        """Check if class is a DeclarativeBase subclass."""
        try:
            registry = getattr(cls, 'registry', None)
            return registry is not None and hasattr(registry, 'mappers')
        except AttributeError:
            return False

    def _preload_all_metadata(self) -> None:
        """Preload metadata for all models in the registry."""
        if not self._is_declarative_base(self._base_class):
            raise TypeError(
                f"{self._base_class.__name__} is not a valid DeclarativeBase. "
                "Please pass the Base class that your models inherit from."
            )

        for mapper in self._base_class.registry.mappers:
            model_class = mapper.class_
            self._metadata_cache[model_class] = ModelMetadata(
                columns={col.key for col in mapper.columns},
                relationships={rel.key for rel in mapper.relationships},
                primary_keys={pk.key for pk in mapper.primary_key},
                relationship_targets={
                    rel.key: rel.mapper.class_
                    for rel in mapper.relationships
                }
            )

    def _get_metadata(self, model_class: type) -> ModelMetadata:
        """Get cached metadata for a model."""
        if model_class not in self._metadata_cache:
            raise TypeError(
                f"Model {model_class.__name__} not found in registry. "
                f"Make sure it inherits from {self._base_class.__name__}."
            )
        return self._metadata_cache[model_class]

    def generate(self, model_class: type, query_string: str) -> list[Any]:
        """
        Generate SQLAlchemy query options from field selection string.

        Args:
            model_class: SQLAlchemy model class to generate options for
            query_string: Simplified field selection syntax, e.g. "{ id name posts { title } }"

        Returns:
            List of SQLAlchemy options that can be passed to .options(*options)

        Raises:
            ParseError: If the query string syntax is invalid
            FieldNotFoundError: If a specified field doesn't exist
            RelationshipNotFoundError: If a specified relationship doesn't exist
        """
        # Check cache
        cache_key = self._make_cache_key(model_class, query_string)
        if cache_key in self._options_cache:
            return self._options_cache[cache_key]

        # Parse and build
        selection = parse_query_string_cached(query_string)
        options = self._build_options(model_class, selection)

        # Cache and return
        self._options_cache[cache_key] = options
        return options

    def _make_cache_key(self, model_class: type, query_string: str) -> str:
        """Create a cache key for the generate result."""
        return f"{model_class.__module__}.{model_class.__name__}:{query_string}"

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
        metadata = self._get_metadata(model_class)

        # Validate and separate fields from relationships
        valid_fields = set()
        for field_name in selection.fields:
            if field_name in metadata.relationships:
                # User forgot to add braces for relationship
                raise RelationshipNotFoundError(
                    f"'{field_name}' is a relationship, use '{field_name} {{ ... }}' syntax"
                )
            if field_name not in metadata.columns:
                raise FieldNotFoundError(
                    f"Field '{field_name}' does not exist on {model_class.__name__}"
                )
            valid_fields.add(field_name)

        # Validate relationships
        for rel_name in selection.relationships:
            if rel_name not in metadata.relationships:
                if rel_name in metadata.columns:
                    raise FieldNotFoundError(
                        f"'{rel_name}' is a column, not a relationship"
                    )
                raise RelationshipNotFoundError(
                    f"Relationship '{rel_name}' does not exist on {model_class.__name__}"
                )

        # 1. Build load_only for scalar fields (with primary key)
        if valid_fields:
            columns = self._ensure_primary_key(model_class, valid_fields, metadata)
            options.append(load_only(*columns))

        # 2. Build selectinload for relationships (recursive)
        for rel_name, nested_selection in selection.relationships.items():
            target_model = metadata.relationship_targets[rel_name]
            rel_attr = getattr(model_class, rel_name)

            nested_options = self._build_options(target_model, nested_selection)
            loader = selectinload(rel_attr).options(*nested_options)
            options.append(loader)

        return options

    def _ensure_primary_key(
        self,
        model_class: type,
        field_names: set[str],
        metadata: ModelMetadata
    ) -> list[Any]:
        """
        Ensure primary key columns are included in load_only.

        SQLAlchemy needs primary keys to properly construct objects.

        Args:
            model_class: SQLAlchemy model class
            field_names: Set of field names to load
            metadata: Cached model metadata

        Returns:
            List of column attributes for load_only
        """
        columns = []

        # Add primary keys first
        for pk_name in sorted(metadata.primary_keys):
            columns.append(getattr(model_class, pk_name))

        # Add other requested fields
        for field_name in sorted(field_names):
            if field_name not in metadata.primary_keys:
                columns.append(getattr(model_class, field_name))

        return columns
