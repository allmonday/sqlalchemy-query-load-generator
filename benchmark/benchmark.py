"""Benchmark script to measure LoadGenerator overhead."""

import time

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    load_only,
    selectinload,
)

from sqlalchemy_load.generator import LoadGenerator

ITERATIONS = 10000


# Define models inline to avoid pytest dependency
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(100))
    posts: Mapped[list["Post"]] = relationship(back_populates="author")


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(String(500))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(String(200))
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    post: Mapped["Post"] = relationship(back_populates="comments")


def bench_native_simple():
    """Native: load_only for simple fields."""
    start = time.perf_counter()
    for _ in range(ITERATIONS):
        options = [load_only(User.id, User.name, User.email)]
    return time.perf_counter() - start


def bench_native_medium():
    """Native: one level nesting."""
    start = time.perf_counter()
    for _ in range(ITERATIONS):
        options = [
            load_only(User.id, User.name),
            selectinload(User.posts).options(load_only(Post.id, Post.title)),
        ]
    return time.perf_counter() - start


def bench_native_complex():
    """Native: two level nesting."""
    start = time.perf_counter()
    for _ in range(ITERATIONS):
        options = [
            load_only(User.id, User.name),
            selectinload(User.posts).options(
                load_only(Post.id, Post.title),
                selectinload(Post.comments).options(
                    load_only(Comment.id, Comment.content)
                ),
            ),
        ]
    return time.perf_counter() - start


def bench_generator(query: str, native_func):
    """Generator: measure cold start and cached performance."""
    generator = LoadGenerator(Base)

    # Cold start (first call)
    cold_start = time.perf_counter()
    generator.generate(User, query)
    cold_time = time.perf_counter() - cold_start

    # Cached (subsequent calls)
    start = time.perf_counter()
    for _ in range(ITERATIONS):
        generator.generate(User, query)
    cached_time = time.perf_counter() - start

    # Native baseline
    native_time = native_func()

    return {
        "query": query,
        "native": native_time,
        "cold": cold_time,
        "cached": cached_time,
    }


def format_result(result: dict):
    """Format a single benchmark result."""
    print(f"  Query: {result['query']}")
    print(f"    Native:          {result['native']*1000:8.3f} ms ({ITERATIONS} iterations)")
    print(f"    Generator (cold): {result['cold']*1000:8.3f} ms (1 iteration)")
    print(f"    Generator (cached): {result['cached']*1000:8.3f} ms ({ITERATIONS} iterations)")
    # Per-call overhead
    native_per_call = result["native"] / ITERATIONS * 1_000_000  # microseconds
    cached_per_call = result["cached"] / ITERATIONS * 1_000_000
    print(f"    Per-call: Native={native_per_call:.2f}μs, Cached={cached_per_call:.2f}μs")
    overhead = ((cached_per_call - native_per_call) / native_per_call) * 100
    print(f"    Overhead: {overhead:+.1f}%")


def main():
    print("=== SQLAlchemy Load Generator Benchmark ===")
    print(f"Iterations: {ITERATIONS}\n")

    # Simple query
    print("[1] Simple Query")
    result = bench_generator("{ name email }", bench_native_simple)
    format_result(result)
    print()

    # Medium query
    print("[2] Medium Query (1 level nesting)")
    result = bench_generator("{ name posts { title } }", bench_native_medium)
    format_result(result)
    print()

    # Complex query
    print("[3] Complex Query (2 level nesting)")
    result = bench_generator(
        "{ name posts { title comments { content } } }", bench_native_complex
    )
    format_result(result)


if __name__ == "__main__":
    main()
