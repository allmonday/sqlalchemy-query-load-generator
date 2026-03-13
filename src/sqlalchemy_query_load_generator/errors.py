"""Custom exceptions for sqlalchemy-load-generator."""


class ParseError(Exception):
    """Raised when the query string syntax is invalid."""

    pass


class FieldNotFoundError(Exception):
    """Raised when a specified field does not exist on the model."""

    pass


class RelationshipNotFoundError(Exception):
    """Raised when a specified relationship does not exist on the model."""

    pass
