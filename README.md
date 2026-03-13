# SQLAlchemy Load Generator

Generate SQLAlchemy query optimization options (`selectinload` + `load_only`) from simplified field selection syntax.

## Why This Library?

SQLAlchemy's query options (`selectinload`, `joinedload`, `load_only`) are powerful but **painful to write**, especially with nested relationships.

### The Problem

**1. Verbose nested syntax**

```python
# Loading User -> Posts -> Comments requires deep nesting
stmt = select(User).options(
    selectinload(User.posts).options(
        load_only(Post.id, Post.title),
        selectinload(Post.comments).options(
            load_only(Comment.id, Comment.content)
        )
    )
)
```

**2. Coupled with query logic**

You must decide what to load at query time, mixing data requirements with query construction. Different API endpoints need different loading strategies, leading to duplicated query code.

**3. Dynamic composition is awkward**

```python
# Conditionally adding options requires extra logic
options = []
if need_posts:
    options.append(selectinload(User.posts))
if need_comments:
    options.append(selectinload(User.posts).selectinload(Post.comments))
stmt = select(User).options(*options)
```

**4. Easy to cause N+1 or over-fetching**

- Forget `selectinload` → N+1 queries
- Load unnecessary fields → wasted memory

### The Solution

This library provides a **declarative syntax** similar to GraphQL:

```python
# Before: verbose, nested, error-prone
stmt = select(User).options(
    selectinload(User.posts).options(
        load_only(Post.id, Post.title),
        selectinload(Post.comments).options(
            load_only(Comment.id, Comment.content)
        )
    )
)

# After: clean, declarative, optimized
generator = LoadGenerator(Base)
options = generator.generate(User, "{ id name posts { title comments { content } } }")
stmt = select(User).options(*options)
```

## Installation

```bash
pip install sqlalchemy-load
```

## Usage

```python
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy_load import LoadGenerator

# Initialize with your DeclarativeBase
generator = LoadGenerator(Base)

# Generate options using simplified syntax
options = generator.generate(User, "{ id name posts { title comments { content } } }")

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
generator.generate(User, "{ id name email }")

# Nested relationships
generator.generate(User, "{ id posts { title content } }")

# Deeply nested
generator.generate(User, "{ id posts { title comments { content author } } }")

# Multiple relationships
generator.generate(User, "{ name posts { title } profile { bio } }")

# Different models with same generator
generator.generate(Post, "{ title content author { name } }")
generator.generate(Comment, "{ content post { title } }")
```

## API

### `LoadGenerator(base_class)`

Create a generator with a SQLAlchemy `DeclarativeBase`. Preloads metadata for all models in the registry for optimal performance.

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

generator = LoadGenerator(Base)
```

### `generator.generate(model_class, query_string) -> list`

Generate SQLAlchemy options from a query string.

```python
options = generator.generate(User, "{ id name posts { title } }")
stmt = select(User).options(*options)
```

## Features

- **Preloaded metadata**: All model metadata is cached at initialization for fast lookups
- **Result caching**: Same query returns cached result, avoiding redundant computation
- **Parse caching**: Query string parsing is cached with `lru_cache`
- **Automatic primary key inclusion**: Primary keys are always included in `load_only`
- **Relationship detection**: Automatically detects SQLAlchemy relationships
- **Nested loading**: Recursively generates `selectinload` with nested `load_only`
- **Error handling**: Clear errors for invalid fields, relationships, or syntax

## Error Handling

```python
from sqlalchemy_load import (
    LoadGenerator,
    ParseError,
    FieldNotFoundError,
    RelationshipNotFoundError,
)

generator = LoadGenerator(Base)

# Syntax error
try:
    generator.generate(User, "{ id name")  # Missing closing brace
except ParseError as e:
    print(f"Syntax error: {e}")

# Field doesn't exist
try:
    generator.generate(User, "{ nonexistent }")
except FieldNotFoundError as e:
    print(f"Field not found: {e}")

# Relationship doesn't exist
try:
    generator.generate(User, "{ notarelationship { id } }")
except RelationshipNotFoundError as e:
    print(f"Relationship not found: {e}")
```

## Requirements

- Python >= 3.10
- SQLAlchemy >= 2.0

## License

MIT
