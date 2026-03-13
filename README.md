# SQLAlchemy Load Generator

Generate SQLAlchemy query optimization options (`selectinload` + `load_only`) from simplified field selection syntax.

## Installation

```bash
pip install sqlalchemy-load-generator
```

## Usage

```python
from sqlalchemy import select
from sqlalchemy_load_generator import LoadGenerator

# Initialize with your SQLAlchemy model
generator = LoadGenerator(User)

# Generate options using simplified syntax
options = generator.generate("{ id name posts { title comments { content } } }")

# Use with SQLAlchemy query
stmt = select(User).options(*options)
```

## Syntax

The simplified syntax is similar to GraphQL but without commas:

```
{ field1 field2 relationship { nested_field } }
```

- Fields are space-separated
- Relationships use `{ }` for nested selection
- Commas are optional and ignored

### Examples

```python
# Simple fields
"{ id name email }"

# Nested relationships
"{ id posts { title content } }"

# Deeply nested
"{ id posts { title comments { content author } } }"

# Multiple relationships
"{ name posts { title } profile { bio } }"
```

## API

### `LoadGenerator(model_class)`

Create a generator for a SQLAlchemy model.

```python
generator = LoadGenerator(User)
```

### `generator.generate(query_string) -> list`

Generate SQLAlchemy options from a query string.

```python
options = generator.generate("{ id name posts { title } }")
stmt = select(User).options(*options)
```

## Features

- **Automatic primary key inclusion**: Primary keys are always included in `load_only` for proper object construction
- **Relationship detection**: Automatically detects SQLAlchemy relationships from model mapper
- **Nested loading**: Recursively generates `selectinload` with nested `load_only`
- **Error handling**: Clear errors for invalid fields, relationships, or syntax

## Error Handling

```python
from sqlalchemy_load_generator import (
    LoadGenerator,
    ParseError,
    FieldNotFoundError,
    RelationshipNotFoundError,
)

generator = LoadGenerator(User)

# Syntax error
try:
    generator.generate("{ id name")  # Missing closing brace
except ParseError as e:
    print(f"Syntax error: {e}")

# Field doesn't exist
try:
    generator.generate("{ nonexistent }")
except FieldNotFoundError as e:
    print(f"Field not found: {e}")

# Relationship doesn't exist
try:
    generator.generate("{ notarelationship { id } }")
except RelationshipNotFoundError as e:
    print(f"Relationship not found: {e}")
```

## Requirements

- Python >= 3.10
- SQLAlchemy >= 2.0

## License

MIT
