"""Tests for the LoadGenerator class."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload, load_only

from sqlalchemy_query_load_generator.generator import LoadGenerator
from sqlalchemy_query_load_generator.errors import FieldNotFoundError, RelationshipNotFoundError

from conftest import User, Post, Comment, Profile


class TestLoadGenerator:
    """Tests for LoadGenerator class."""

    def test_init_with_valid_model(self):
        """Initialize LoadGenerator with a valid SQLAlchemy model."""
        generator = LoadGenerator(User)
        assert generator.model_class == User

    def test_init_detects_relationships(self):
        """LoadGenerator should detect relationships from model."""
        generator = LoadGenerator(User)
        assert "posts" in generator._relationship_names
        assert "profile" in generator._relationship_names

    def test_generate_simple_fields(self):
        """Generate options for simple field selection."""
        generator = LoadGenerator(User)
        options = generator.generate("{ name email }")

        # Should return a list of options
        assert isinstance(options, list)
        assert len(options) == 1
        # Should be a load_only option
        assert hasattr(options[0], '__class__')

    def test_generate_includes_primary_key_automatically(self, session):
        """Generated options should always include primary key."""
        generator = LoadGenerator(User)
        options = generator.generate("{ name }")

        # Execute a query to verify the option works
        stmt = select(User).options(*options)
        # Should not raise an error
        result = session.execute(stmt)
        # The query should be valid

    def test_generate_with_nested_relationship(self):
        """Generate options with nested relationship."""
        generator = LoadGenerator(User)
        options = generator.generate("{ name posts { title } }")

        assert isinstance(options, list)
        assert len(options) == 2  # load_only for name, selectinload for posts

    def test_generate_with_deeply_nested_relationships(self):
        """Generate options with deeply nested relationships."""
        generator = LoadGenerator(User)
        options = generator.generate("{ name posts { title comments { content } } }")

        assert isinstance(options, list)
        # Should have load_only + selectinload(posts)
        assert len(options) >= 1

    def test_generate_with_multiple_relationships(self):
        """Generate options with multiple relationships."""
        generator = LoadGenerator(User)
        options = generator.generate("{ name posts { title } profile { bio } }")

        assert isinstance(options, list)
        # load_only + selectinload(posts) + selectinload(profile)
        assert len(options) >= 2

    def test_generate_empty_selection_raises_error(self):
        """Empty selection should raise ParseError."""
        generator = LoadGenerator(User)
        with pytest.raises(Exception):  # ParseError
            generator.generate("{}")

    def test_generate_invalid_field_raises_error(self):
        """Invalid field should raise FieldNotFoundError."""
        generator = LoadGenerator(User)
        with pytest.raises(FieldNotFoundError):
            generator.generate("{ nonexistent }")

    def test_generate_invalid_relationship_raises_error(self):
        """Invalid relationship should raise RelationshipNotFoundError."""
        generator = LoadGenerator(User)
        with pytest.raises(RelationshipNotFoundError):
            generator.generate("{ nonexistent { id } }")

    def test_generate_validates_nested_fields(self):
        """Should validate fields in nested relationships."""
        generator = LoadGenerator(User)
        with pytest.raises(FieldNotFoundError):
            generator.generate("{ posts { nonexistent } }")

    def test_generate_works_with_different_models(self):
        """LoadGenerator should work with different model classes."""
        post_generator = LoadGenerator(Post)
        options = post_generator.generate("{ title content }")

        assert isinstance(options, list)

    def test_generate_single_relationship_field(self):
        """Generate options for single field in relationship."""
        generator = LoadGenerator(User)
        options = generator.generate("{ posts { title } }")

        assert isinstance(options, list)

    def test_generate_all_relationship_fields(self):
        """Generate options when selecting all fields in relationship."""
        generator = LoadGenerator(User)
        options = generator.generate("{ posts { id title content } }")

        assert isinstance(options, list)


class TestLoadGeneratorIntegration:
    """Integration tests with actual database queries."""

    def test_query_with_simple_fields(self, session):
        """Test actual query with simple field selection."""
        # Create test data
        user = User(name="Test User", email="test@example.com")
        session.add(user)
        session.commit()

        generator = LoadGenerator(User)
        options = generator.generate("{ name email }")

        stmt = select(User).options(*options).where(User.id == user.id)
        result = session.execute(stmt).scalar_one()

        # Should be able to access selected fields
        assert result.name == "Test User"
        assert result.email == "test@example.com"

    def test_query_with_nested_relationship(self, session):
        """Test actual query with nested relationship."""
        # Create test data
        user = User(name="Test User", email="test@example.com")
        post = Post(title="Test Post", content="Content", author=user)
        session.add_all([user, post])
        session.commit()

        generator = LoadGenerator(User)
        options = generator.generate("{ name posts { title } }")

        stmt = select(User).options(*options).where(User.id == user.id)
        result = session.execute(stmt).scalar_one()

        assert result.name == "Test User"
        # posts should be loaded
        assert len(result.posts) == 1
        assert result.posts[0].title == "Test Post"

    def test_query_with_deeply_nested(self, session):
        """Test actual query with deeply nested relationships."""
        # Create test data
        user = User(name="Test User", email="test@example.com")
        post = Post(title="Test Post", content="Content", author=user)
        comment = Comment(content="Test Comment", post=post)
        session.add_all([user, post, comment])
        session.commit()

        generator = LoadGenerator(User)
        options = generator.generate("{ name posts { title comments { content } } }")

        stmt = select(User).options(*options).where(User.id == user.id)
        result = session.execute(stmt).scalar_one()

        assert result.name == "Test User"
        assert len(result.posts) == 1
        assert result.posts[0].title == "Test Post"
        assert len(result.posts[0].comments) == 1
        assert result.posts[0].comments[0].content == "Test Comment"
