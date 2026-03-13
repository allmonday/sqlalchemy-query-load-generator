"""Test fixtures and models for sqlalchemy-load-generator tests."""

import pytest
from sqlalchemy import Table, Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session


class Base(DeclarativeBase):
    """Base class for test models."""
    pass


# Many-to-many association table
user_groups = Table(
    'user_groups',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id'), primary_key=True)
)


class User(Base):
    """Test User model."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(100))

    # Relationships
    posts: Mapped[list["Post"]] = relationship(back_populates="author")
    profile: Mapped["Profile"] = relationship(back_populates="user")
    groups: Mapped[list["Group"]] = relationship(secondary=user_groups, back_populates="members")


class Post(Base):
    """Test Post model."""
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(String(500))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Relationships
    author: Mapped["User"] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")


class Comment(Base):
    """Test Comment model."""
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(String(200))
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))

    # Relationships
    post: Mapped["Post"] = relationship(back_populates="comments")


class Profile(Base):
    """Test Profile model (one-to-one with User)."""
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    bio: Mapped[str] = mapped_column(String(200))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="profile")


class Group(Base):
    """Test Group model (many-to-many with User)."""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

    # Relationships
    members: Mapped[list["User"]] = relationship(secondary=user_groups, back_populates="groups")


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
