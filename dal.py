# dal.py
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session, joinedload

from models import Author, Book, BookAuthor, Review

# Number of cards per page in UI listings.
PAGE_SIZE = 12

# ---------------------------------------------------------------------------
# Utilities / lookups
# ---------------------------------------------------------------------------

def _get_or_create_author(session: Session, name: str | None) -> Author | None:
    """
    Return an Author by (case-insensitive) name, creating it if needed.
    Empty/None names return None.
    """
    if not name:
        return None
    norm = name.strip()
    if not norm:
        return None

    author = session.scalar(
        select(Author).where(func.lower(Author.name) == norm.lower())
    )
    if author:
        return author

    author = Author(name=norm)
    session.add(author)
    session.flush()  # ensure author.id exists
    return author


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------

def create_book(
    session: Session,
    *,
    title: str,
    year: Optional[int] = None,
    description: Optional[str] = None,
    cover_url: Optional[str] = None,
    language: Optional[str] = None,
    authors: Optional[Sequence[str]] = None,
    height_cm: Optional[int] = None,
    width_cm: Optional[int] = None,
    thickness_cm: Optional[int] = None,
    pages: Optional[int] = None,
    format: Optional[str] = None,
) -> Book:
    """
    Create a Book (and any missing Authors), attach relationships, and return it.

    Note: this function calls session.flush() but does NOT commit; the caller
    should manage transaction boundaries.
    """
    if not title or not title.strip():
        raise ValueError("title is required")

    book = Book(
        title=title.strip(),
        year=year,
        description=(description or None),
        cover_url=(cover_url or None),
        language=(language or None),
        height_cm=height_cm,
        width_cm=width_cm,
        thickness_cm=thickness_cm,
        pages=pages,
        format=(format or None),
    )

    for n in (authors or []):
        a = _get_or_create_author(session, n)
        if a:
            book.authors.append(a)

    session.add(book)
    session.flush()  # ensures book.id is available
    return book


def update_book_dimensions(
    session: Session,
    book_id: int,
    *,
    height_cm: Optional[int] = None,
    width_cm: Optional[int] = None,
    thickness_cm: Optional[int] = None,
    pages: Optional[int] = None,
    format: Optional[str] = None,
) -> Book | None:
    """
    Patch dimension-ish fields on a book. Returns the updated Book or None if not found.
    """
    book = session.get(Book, book_id)
    if not book:
        return None

    if height_cm is not None:
        book.height_cm = height_cm
    if width_cm is not None:
        book.width_cm = width_cm
    if thickness_cm is not None:
        book.thickness_cm = thickness_cm
    if pages is not None:
        book.pages = pages
    if format is not None:
        book.format = format

    session.flush()
    return book


# ---------------------------------------------------------------------------
# Queries / listing
# ---------------------------------------------------------------------------

def list_books(
    session: Session,
    *,
    q: Optional[str] = None,
    page: int = 1,
) -> Tuple[List[Book], int]:
    """
    Paginated list of books with authors eagerly loaded.
    Returns (items, total_count) where items is a list[Book].

    - q: optional case-insensitive title substring filter
    - page: 1-based page index
    """
    page = max(1, int(page))

    base_stmt = select(Book).options(joinedload(Book.authors))

    if q:
        like = f"%{q.lower()}%"
        base_stmt = base_stmt.where(func.lower(Book.title).like(like))

    # total count
    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = int(session.scalar(total_stmt) or 0)

    items = (
        session.execute(
            base_stmt.order_by(Book.title.asc())
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
        .unique()
        .scalars()
        .all()
    )
    return items, total


def top_recent_reviews(session: Session, limit: int = 10) -> List[Review]:
    """
    Most recent reviews, newest first.
    """
    stmt = select(Review).order_by(Review.created_at.desc()).limit(limit)
    return session.execute(stmt).scalars().all()


# ---------------------------------------------------------------------------
# Reviews (one per user per book)
# ---------------------------------------------------------------------------

def get_user_review(session: Session, user_id: int, book_id: int) -> Review | None:
    """
    Retrieve a single user's review of a book, if any.
    """
    return session.scalar(
        select(Review).where(Review.user_id == user_id, Review.book_id == book_id)
    )


def upsert_review(
    session: Session, user_id: int, book_id: int, rating: int, text_value: str | None
) -> Review:
    """
    Create or update a user's review for a book. Returns the Review.

    Note: validates rating range (1..5) if present.
    """
    if rating is not None and not (1 <= int(rating) <= 5):
        raise ValueError("rating must be in 1..5")

    rv = get_user_review(session, user_id, book_id)
    if rv:
        rv.rating = rating
        rv.text = text_value
        session.flush()
        return rv

    rv = Review(user_id=user_id, book_id=book_id, rating=rating, text=text_value)
    session.add(rv)
    session.flush()
    return rv


def list_user_reviews(session: Session, user_id: int) -> List[Review]:
    """
    All reviews by a user, newest first. Eager-loads minimal Book fields.
    """
    stmt = (
        select(Review)
        .options(
            joinedload(Review.book).load_only(Book.id, Book.title)
        )
        .where(Review.user_id == user_id)
        .order_by(Review.created_at.desc())
    )
    return session.execute(stmt).scalars().all()


def delete_user_review(session: Session, user_id: int, book_id: int) -> int:
    """
    Delete a user's review of a book. Returns number of rows deleted (0 or 1).
    """
    res = session.execute(
        delete(Review).where(Review.user_id == user_id, Review.book_id == book_id)
    )
    return int(res.rowcount or 0)


def rating_summary_for_books(
    session: Session, book_ids: Sequence[int]
) -> Dict[int, Tuple[float, int]]:
    """
    Aggregate ratings for the given books.
    Returns {book_id: (avg_rating, n_reviews)}.
    """
    if not book_ids:
        return {}

    rows = session.execute(
        select(Review.book_id, func.avg(Review.rating), func.count(Review.id))
        .where(Review.book_id.in_(list(book_ids)))
        .group_by(Review.book_id)
    ).all()

    return {bid: (float(avg), int(n)) for bid, avg, n in rows}


# ---------------------------------------------------------------------------
# Analytics helpers (raw SQL for viz)
# ---------------------------------------------------------------------------

def top_chonkers_sql():
    """
    Raw SQL for the 20 largest volumes (cm³) among books with complete dimensions.
    """
    return text(
        """
        SELECT
          id,
          title,
          (height_cm * width_cm * thickness_cm) / 1000.0 AS volume_cm3
        FROM books
        WHERE height_cm IS NOT NULL
          AND width_cm IS NOT NULL
          AND thickness_cm IS NOT NULL
        ORDER BY volume_cm3 DESC
        LIMIT 20
        """
    )


def shelf_space_by_user_treemap_sql():
    """
    One row per (user, book) with computed volume in cm³.
    A book counts toward each user who reviewed it.
    """
    return text(
        """
        SELECT
          u.username,
          b.id        AS book_id,
          b.title,
          (b.height_cm * b.width_cm * b.thickness_cm) / 1000.0 AS volume_cm3
        FROM reviews r
        JOIN users   u ON u.id = r.user_id
        JOIN books   b ON b.id = r.book_id
        WHERE b.height_cm IS NOT NULL
          AND b.width_cm  IS NOT NULL
          AND b.thickness_cm IS NOT NULL
        """
    )


# ---------------------------------------------------------------------------
# OpenLibrary (or other API) ingest
# ---------------------------------------------------------------------------

def find_book_by_external_id(session: Session, external_id: str | None) -> Book | None:
    """
    Lookup Book by an external API id.
    """
    if not external_id:
        return None
    return session.scalar(select(Book).where(Book.external_id == external_id))


def create_book_from_api(session: Session, payload: dict) -> Tuple[Book, bool]:
    """
    Create a Book from an external payload (e.g., OpenLibrary).
    Returns (book, created_bool). Does not commit.
    """
    # If external_id is present, avoid duplicates.
    external_id = payload.get("external_id")
    if external_id:
        existing = find_book_by_external_id(session, external_id)
        if existing:
            return existing, False

    book = Book(
        external_id=external_id,
        title=payload.get("title"),
        year=payload.get("year"),
        description=payload.get("description"),
        cover_url=payload.get("cover_url"),
        language=payload.get("language"),
        pages=payload.get("pages"),
        height_cm=payload.get("height_cm"),
        width_cm=payload.get("width_cm"),
        thickness_cm=payload.get("thickness_cm"),
    )

    session.add(book)
    session.flush()  # book.id becomes available

    # Authors
    for name in payload.get("authors", []) or []:
        author = session.scalar(select(Author).where(Author.name == name))
        if not author:
            author = Author(name=name)
            session.add(author)
            session.flush()
        session.add(BookAuthor(book_id=book.id, author_id=author.id))

    session.flush()
    return book, True


# ---------------------------------------------------------------------------
# Deletes
# ---------------------------------------------------------------------------

def delete_book(session: Session, book_id: int) -> int:
    """
    Hard-delete a book and its dependent rows.
    Returns number of Book rows deleted (0 or 1).

    Note: this assumes FKs do NOT have ON DELETE CASCADE.
    """
    # Remove dependents first
    session.execute(delete(Review).where(Review.book_id == book_id))
    session.execute(delete(BookAuthor).where(BookAuthor.book_id == book_id))
    res = session.execute(delete(Book).where(Book.id == book_id))
    return int(res.rowcount or 0)
