"""
=============================================================
Models
=============================================================
This file defines the SQLAlchemy ORM models.
Each class maps to a table; relationships map to foreign keys.

- User -> Review -> Book (users write reviews on books)
- Book <-> Author          (many-to-many via book_authors)

Conventions:
- Integer sizes are in millimeters (height_cm, width_cm, thickness_cm).
- `external_id` stores an external provider key (Open Library).
- We keep (title, year) unique to reduce duplicates.
- Relationships use cascade where appropriate (e.g., deleting a Book deletes its Reviews).
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

class User(Base):
    """
    Represents an account capable of writing reviews.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reviews: Mapped[List["Review"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Author(Base):
    """
    Represents a book author.
    """
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)

    books: Mapped[List["Book"]] = relationship(
        secondary="book_authors", back_populates="authors"
    )

class Book(Base):
    """
    Central entity of the app: a book in your catalog.
    """
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    year: Mapped[Optional[int]]
    description: Mapped[Optional[str]] = mapped_column(Text)
    cover_url: Mapped[Optional[str]] = mapped_column(String(500))
    language: Mapped[Optional[str]] = mapped_column(String(10))

    # physical dimensions
    height_cm: Mapped[Optional[int]]
    width_cm: Mapped[Optional[int]]
    thickness_cm: Mapped[Optional[int]]
    pages: Mapped[Optional[int]]
    format: Mapped[Optional[str]] = mapped_column(String(30))

    authors: Mapped[List["Author"]] = relationship(
        secondary="book_authors", back_populates="books"
    )

    reviews: Mapped[List["Review"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("title", "year", name="uq_book_title_year"),
    )


class BookAuthor(Base):
    """
    Association table linking Books to Authors (many-to-many).
    """
    __tablename__ = "book_authors"

    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), primary_key=True)

class Review(Base):
    """
    User-submitted review for a Book.
    """
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1..5
    text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="reviews")
    book: Mapped["Book"] = relationship(back_populates="reviews")

    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_user_book_once"),
    )

