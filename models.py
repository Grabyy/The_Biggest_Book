# models.py
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reviews: Mapped[List["Review"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    books: Mapped[List["Book"]] = relationship(secondary="book_authors", back_populates="authors")

class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    books: Mapped[List["Book"]] = relationship(secondary="book_subjects", back_populates="subjects")

class Book(Base):
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
        UniqueConstraint("title", "year", name="uq_book_title_year"),
    )

class BookAuthor(Base):
    __tablename__ = "book_authors"
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), primary_key=True)

class BookSubject(Base):
    __tablename__ = "book_subjects"
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), primary_key=True)

class Review(Base):
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

