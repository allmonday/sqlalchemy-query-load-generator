"""Metadata caching utilities for SQLAlchemy models."""

from dataclasses import dataclass
from typing import Type


@dataclass
class ModelMetadata:
    """Cached metadata for a SQLAlchemy model.

    Attributes:
        columns: Set of column names on the model
        relationships: Set of relationship names on the model
        primary_keys: Set of primary key column names
        relationship_targets: Mapping of relationship name to target model class
    """
    columns: set[str]
    relationships: set[str]
    primary_keys: set[str]
    relationship_targets: dict[str, Type]
