"""Tests for the LoadGenerator class."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload, load_only

from sqlalchemy_load.generator import LoadGenerator
from sqlalchemy_load.errors import FieldNotFoundError, RelationshipNotFoundError

from conftest import Base, User, Post, Comment, Profile


class TestLoadGenerator:
    """Tests for LoadGenerator class."""

    def test_init_with_valid_base(self):
        """Initialize LoadGenerator with a valid DeclarativeBase."""
        generator = LoadGenerator(Base)
        assert generator._base_class == Base

    def test_init_with_invalid_base(self):
        """Passing non-DeclarativeBase should raise TypeError."""
        with pytest.raises(TypeError, match="not a valid DeclarativeBase"):
            LoadGenerator(object)

        with pytest.raises(TypeError, match="not a valid DeclarativeBase"):
            LoadGenerator(str)

    def test_init_preloads_all_models(self):
        """LoadGenerator should preload metadata for all models."""
        generator = LoadGenerator(Base)
        # All models should be cached
        assert User in generator._metadata_cache
        assert Post in generator._metadata_cache
        assert Comment in generator._metadata_cache
        assert Profile in generator._metadata_cache

    def test_init_detects_relationships(self):
        """LoadGenerator should detect relationships from model metadata."""
        generator = LoadGenerator(Base)
        user_metadata = generator._metadata_cache[User]
        assert "posts" in user_metadata.relationships
        assert "profile" in user_metadata.relationships

    def test_generate_simple_fields(self):
        """Generate options for simple field selection."""
        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ name email }")

        # Should return a list of options
        assert isinstance(options, list)
        assert len(options) == 1
        # Should be a load_only option
        assert hasattr(options[0], '__class__')

    def test_generate_includes_primary_key_automatically(self, session):
        """Generated options should always include primary key."""
        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ name }")

        # Execute a query to verify the option works
        stmt = select(User).options(*options)
        # Should not raise an error
        result = session.execute(stmt)
        # The query should be valid

    def test_generate_with_nested_relationship(self):
        """Generate options with nested relationship."""
        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ name posts { title } }")

        assert isinstance(options, list)
        assert len(options) == 2  # load_only for name, selectinload for posts

    def test_generate_with_deeply_nested_relationships(self):
        """Generate options with deeply nested relationships."""
        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ name posts { title comments { content } } }")

        assert isinstance(options, list)
        # Should have load_only + selectinload(posts)
        assert len(options) >= 1

    def test_generate_with_multiple_relationships(self):
        """Generate options with multiple relationships."""
        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ name posts { title } profile { bio } }")

        assert isinstance(options, list)
        # load_only + selectinload(posts) + selectinload(profile)
        assert len(options) >= 2

    def test_generate_empty_selection_raises_error(self):
        """Empty selection should raise ParseError."""
        generator = LoadGenerator(Base)
        with pytest.raises(Exception):  # ParseError
            generator.generate(User, "{}")

    def test_generate_invalid_field_raises_error(self):
        """Invalid field should raise FieldNotFoundError."""
        generator = LoadGenerator(Base)
        with pytest.raises(FieldNotFoundError):
            generator.generate(User, "{ nonexistent }")

    def test_generate_invalid_relationship_raises_error(self):
        """Invalid relationship should raise RelationshipNotFoundError."""
        generator = LoadGenerator(Base)
        with pytest.raises(RelationshipNotFoundError):
            generator.generate(User, "{ nonexistent { id } }")

    def test_generate_validates_nested_fields(self):
        """Should validate fields in nested relationships."""
        generator = LoadGenerator(Base)
        with pytest.raises(FieldNotFoundError):
            generator.generate(User, "{ posts { nonexistent } }")

    def test_generate_works_with_different_models(self):
        """LoadGenerator should work with different model classes using same instance."""
        generator = LoadGenerator(Base)

        # Generate for User
        user_options = generator.generate(User, "{ name email }")
        assert isinstance(user_options, list)

        # Generate for Post using same generator
        post_options = generator.generate(Post, "{ title content }")
        assert isinstance(post_options, list)

    def test_generate_single_relationship_field(self):
        """Generate options for single field in relationship."""
        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ posts { title } }")

        assert isinstance(options, list)

    def test_generate_all_relationship_fields(self):
        """Generate options when selecting all fields in relationship."""
        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ posts { id title content } }")

        assert isinstance(options, list)

    def test_generate_result_caching(self):
        """Same query should return cached result."""
        generator = LoadGenerator(Base)

        options1 = generator.generate(User, "{ name email }")
        options2 = generator.generate(User, "{ name email }")

        # Should return the same cached object
        assert options1 is options2

    def test_generate_different_queries_not_cached(self):
        """Different queries should return different results."""
        generator = LoadGenerator(Base)

        options1 = generator.generate(User, "{ name }")
        options2 = generator.generate(User, "{ email }")

        # Should return different objects
        assert options1 is not options2

    def test_generate_model_not_in_registry(self):
        """Generating for unregistered model should raise TypeError."""
        from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

        generator = LoadGenerator(Base)

        # Create a different Base (different registry)
        class OtherBase(DeclarativeBase):
            pass

        class ExternalModel(OtherBase):
            __tablename__ = "external"
            id: Mapped[int] = mapped_column(primary_key=True)

        with pytest.raises(TypeError, match="not found in registry"):
            generator.generate(ExternalModel, "{ id }")

    def test_generate_only_relationships_no_fields(self):
        """Query with only relationships, no scalar fields."""
        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ posts { title } profile { bio } }")

        assert isinstance(options, list)
        # Should have 2 selectinload, no load_only
        assert len(options) == 2

    def test_generate_relationship_used_as_field_error(self):
        """Using relationship without braces should give helpful error."""
        generator = LoadGenerator(Base)
        with pytest.raises(RelationshipNotFoundError) as exc:
            generator.generate(User, "{ posts }")
        assert "use 'posts { ... }' syntax" in str(exc.value)

    def test_generate_field_used_as_relationship_error(self):
        """Using field with braces should give helpful error."""
        generator = LoadGenerator(Base)
        with pytest.raises(FieldNotFoundError) as exc:
            generator.generate(User, "{ name { something } }")
        assert "column, not a relationship" in str(exc.value)


class TestLoadGeneratorIntegration:
    """Integration tests with actual database queries."""

    def test_query_with_simple_fields(self, session):
        """Test actual query with simple field selection."""
        # Create test data
        user = User(name="Test User", email="test@example.com")
        session.add(user)
        session.commit()

        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ name email }")

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

        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ name posts { title } }")

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

        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ name posts { title comments { content } } }")

        stmt = select(User).options(*options).where(User.id == user.id)
        result = session.execute(stmt).scalar_one()

        assert result.name == "Test User"
        assert len(result.posts) == 1
        assert result.posts[0].title == "Test Post"
        assert len(result.posts[0].comments) == 1
        assert result.posts[0].comments[0].content == "Test Comment"

    def test_query_with_one_to_one_relationship(self, session):
        """Test actual query with one-to-one relationship (uselist=False)."""
        # Create test data
        user = User(name="Test User", email="test@example.com")
        profile = Profile(bio="Test Bio", user=user)
        session.add_all([user, profile])
        session.commit()

        generator = LoadGenerator(Base)
        options = generator.generate(User, "{ name profile { bio } }")

        stmt = select(User).options(*options).where(User.id == user.id)
        result = session.execute(stmt).scalar_one()

        assert result.name == "Test User"
        # profile should be loaded (one-to-one)
        assert result.profile is not None
        assert result.profile.bio == "Test Bio"

    def test_query_with_reverse_relationship(self, session):
        """Test loading reverse relationship (Post.author -> User)."""
        # Create test data
        user = User(name="Test User", email="test@example.com")
        post = Post(title="Test Post", content="Content", author=user)
        session.add_all([user, post])
        session.commit()

        generator = LoadGenerator(Base)
        options = generator.generate(Post, "{ title author { name } }")

        stmt = select(Post).options(*options).where(Post.id == post.id)
        result = session.execute(stmt).scalar_one()

        assert result.title == "Test Post"
        # author should be loaded
        assert result.author is not None
        assert result.author.name == "Test User"

    def test_query_without_load_only_still_works(self, session):
        """Query with only relationships should still work correctly."""
        # Create test data
        user = User(name="Test User", email="test@example.com")
        post = Post(title="Test Post", content="Content", author=user)
        profile = Profile(bio="Test Bio", user=user)
        session.add_all([user, post, profile])
        session.commit()

        generator = LoadGenerator(Base)
        # Only relationships, no scalar fields
        options = generator.generate(User, "{ posts { title } profile { bio } }")

        stmt = select(User).options(*options).where(User.id == user.id)
        result = session.execute(stmt).scalar_one()

        # Should still be able to access id (primary key is always loaded)
        assert result.id == user.id
        # Relationships should be loaded
        assert len(result.posts) == 1
        assert result.posts[0].title == "Test Post"
        assert result.profile.bio == "Test Bio"
