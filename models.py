"""
=============================================================
Models
=============================================================
This file defines the SQLAlchemy ORM models.
Each class maps to a table; relationships map to foreign keys.

- User -> Review -> Book (users write reviews on books)
- Book <-> Author       (many-to-many via book_authors)
- Book <-> Subject      (many-to-many via book_subjects)

Conventions:
- Integer sizes are in millimeters (height_mm, width_mm, thickness_mm).
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
    Columns:
    - id: PK
    - username: unique handle for the user (indexed)
    - created_at: creation timestamp

    Relationships:
    - reviews: one-to-many -> Review.user (cascade delete-orphan)
    """
__tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reviews: Mapped[List["Review"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Author(Base):
    """
    Represents a book author.
    Columns:
    - id: PK
    - name: unique author name (indexed)

    Relationships:
    - books: many-to-many with Book via association table book_authors
    """
__tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    books: Mapped[List["Book"]] = relationship(secondary="book_authors", back_populates="authors")

class Subject(Base):
    """
    Represents a subject/genre/tag for books (e.g., 'Science Fiction').
    Columns:
    - id: PK
    - name: unique subject name (indexed)

    Relationships:
    - books: many-to-many with Book via association table book_subjects
    """
__tablename__ = "subjects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    books: Mapped[List["Book"]] = relationship(secondary="book_subjects", back_populates="subjects")

class Book(Base):
    """
    Central entity of the app: a book in your catalog.

    Core metadata:
    - id: PK
    - external_id: external provider key (e.g., '/works/OL123W' or '/books/OL123M')
    - title, year, description, cover_url, language

    Physical properties (mm):
    - height_mm, width_mm, thickness_mm — used to compute volume (cm³ = h*w*t/1000)
    - pages: page count (helps estimate thickness when missing)
    - format: paperback/hardcover/ebook/other

    Relationships:
    - authors: M:N to Author via book_authors
    - subjects: M:N to Subject via book_subjects
    - reviews: 1:M to Review

    Constraints:
    - UniqueConstraint(title, year) — soft dedupe to avoid exact duplicates for the same year.
    """
__tablename__ = "books"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # external IDs from APIs (e.g., OLID or Google volumeId)
    external_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    year: Mapped[Optional[int]]
    description: Mapped[Optional[str]] = mapped_column(Text)
    cover_url: Mapped[Optional[str]] = mapped_column(String(500))
    language: Mapped[Optional[str]] = mapped_column(String(10))

    # physical dimensions (for fun graphs)
    height_mm: Mapped[Optional[int]]
    width_mm: Mapped[Optional[int]]
    thickness_mm: Mapped[Optional[int]]
    pages: Mapped[Optional[int]]
    format: Mapped[Optional[str]] = mapped_column(String(30))  # hardcover/paperback/etc.

    authors: Mapped[List["Author"]] = relationship(secondary="book_authors", back_populates="books")
    subjects: Mapped[List["Subject"]] = relationship(secondary="book_subjects", back_populates="books")
    reviews: Mapped[List["Review"]] = relationship(back_populates="book", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("title", "year", name="uq_book_title_year"),  # soft dedupe: avoid duplicate (title, year) rows
    )

class BookAuthor(Base):
    """
    Association table linking Books to Authors (many-to-many).
    Composite primary key: (book_id, author_id).
    """
__tablename__ = "book_authors"
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), primary_key=True)

class BookSubject(Base):
    """
    Association table linking Books to Subjects (many-to-many).
    Composite primary key: (book_id, subject_id).
    """
__tablename__ = "book_subjects"
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), primary_key=True)

class Review(Base):
    """
    User-submitted review for a Book.

    Columns:
    - id: PK
    - user_id: FK -> users.id
    - book_id: FK -> books.id
    - rating: integer in [1..5]
    - text: optional free text
    - created_at: timestamp

    Relationships:
    - user: many-to-one -> User
    - book: many-to-one -> Book

    Constraints:
    - UniqueConstraint(user_id, book_id) — a user can review a given book at most once.
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
        UniqueConstraint("user_id", "book_id", name="uq_user_book_once"),  # one review per user per book
    )

