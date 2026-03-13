"""Test fixtures and models for sqlalchemy-load-generator tests."""

import pytest
from sqlalchemy import Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session


class Base(DeclarativeBase):
    """Base class for test models."""
    pass


class User(Base):
    """Test User model."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255))

    # Relationships
    posts: Mapped[list["Post"]] = relationship(back_populates="author")
    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False)


class Post(Base):
    """Test Post model."""
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(String(2000))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Relationships
    author: Mapped["User"] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")


class Comment(Base):
    """Test Comment model."""
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(String(1000))
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))

    # Relationships
    post: Mapped["Post"] = relationship(back_populates="comments")


class Profile(Base):
    """Test Profile model."""
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    bio: Mapped[str] = mapped_column(String(500))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="profile")


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a session for testing."""
    with Session(engine) as session:
        yield session
