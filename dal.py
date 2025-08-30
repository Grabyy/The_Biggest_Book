# dal.py
from models import Book, Author, Review, BookAuthor
from sqlalchemy import select, func, desc, text, delete
from sqlalchemy.orm import joinedload
from typing import List, Optional, Tuple

PAGE_SIZE = 12  # grid cards per page

# ---------- lookups / get-or-create ----------

def _get_or_create_author(session, name: str) -> Author:
    name = (name or "").strip()
    if not name:
        return None
    a = session.scalar(select(Author).where(func.lower(Author.name) == name.lower()))
    if a:
        return a
    a = Author(name=name)
    session.add(a)
    session.flush()
    return a

# ---------- create / update ----------

def create_book(
    session,
    *,
    title: str,
    year: Optional[int] = None,
    description: Optional[str] = None,
    cover_url: Optional[str] = None,
    language: Optional[str] = None,
    authors: List[str] = None,
    height_cm: Optional[int] = None,
    width_cm: Optional[int] = None,
    thickness_cm: Optional[int] = None,
    pages: Optional[int] = None,
    format: Optional[str] = None,
):
    authors = authors or []
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
    for n in authors:
        a = _get_or_create_author(session, n)
        if a:
            book.authors.append(a)
    session.add(book)
    session.flush()
    return book

def update_book_dimensions(session, book_id: int, *, height_cm=None, width_cm=None, thickness_cm=None, pages=None, format=None):
    book = session.get(Book, book_id)
    if not book:
        return None
    if height_cm is not None: book.height_cm = height_cm
    if width_cm is not None: book.width_cm = width_cm
    if thickness_cm is not None: book.thickness_cm = thickness_cm
    if pages is not None: book.pages = pages
    if format is not None: book.format = format
    session.flush()
    return book

# ---------- queries / listing ----------

def list_books(
    session,
    *,
    q: Optional[str] = None,
    page: int = 1,
) -> Tuple[List[Book], int]:
    stmt = select(Book).options(
        joinedload(Book.authors),
    )

    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Book.title).like(like))

    # total count
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.scalar(total_stmt) or 0

    items = (
        session.execute(
            stmt.order_by(Book.title.asc())
                .limit(PAGE_SIZE)
                .offset((page - 1) * PAGE_SIZE)
        )
        .unique()
        .scalars()
        .all()
    )
    return items, total

def top_recent_reviews(session, limit: int = 10):
    stmt = (
        select(Review)
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    return session.execute(stmt).scalars().all()

# --- Reviews (one per user per book) ---

def upsert_review(session, user_id: int, book_id: int, rating: int, text_value: str | None):
    rv = session.scalar(
        select(Review).where(Review.user_id == user_id, Review.book_id == book_id)
    )
    if rv:
        rv.rating = rating
        rv.text = text_value
        session.flush()
        return rv
    rv = Review(user_id=user_id, book_id=book_id, rating=rating, text=text_value)
    session.add(rv)
    session.flush()
    return rv


# replace your list_user_reviews with this:
def list_user_reviews(session, user_id: int):
    stmt = (
        select(Review)
        .options(
            joinedload(Review.book)  # eager-load the related Book
            .load_only(Book.id, Book.title)  # optional: only what you need
        )
        .where(Review.user_id == user_id)
        .order_by(Review.created_at.desc())
    )
    return session.execute(stmt).scalars().all()

# --- Analytics helpers ---

def top_chonkers_sql():
    # Largest volumes (needs dimensions filled)
    return text("""
      SELECT
        id, title,
        (height_cm*width_cm*thickness_cm)/1000.0 AS volume_cm3
      FROM books
      WHERE height_cm IS NOT NULL AND width_cm IS NOT NULL AND thickness_cm IS NOT NULL
      ORDER BY volume_cm3 DESC
      LIMIT 20
    """)

def shelf_space_by_user_treemap_sql():
    """
    One row per (user, book) with computed volume in cm³.
    A book counts toward each user who reviewed it.
    """
    return text("""
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
    """)

def find_book_by_external_id(session, external_id: str | None):
    if not external_id:
        return None
    return session.scalar(select(Book).where(Book.external_id == external_id))

def create_book_from_api(session, payload: dict):
    """
    Create a Book from the OpenLibrary payload.
    """

    book = Book(
        external_id=payload.get("external_id"),
        title=payload.get("title"),
        year=payload.get("year"),
        description=payload.get("description"),
        cover_url=payload.get("cover_url"),
        language=payload.get("language"),
        pages=payload.get("pages"),
        height_cm=payload.get("height_cm"),
        width_cm=payload.get("width_cm"),
        thickness_cm=payload.get("thickness_cm")
    )

    session.add(book)
    session.flush()  # book.id becomes available

    # Authors
    for name in payload.get("authors", []):
        author = session.query(Author).filter_by(name=name).first()
        if not author:
            author = Author(name=name)
            session.add(author)
            session.flush()
        session.add(BookAuthor(book_id=book.id, author_id=author.id))

    session.commit()

    return book, True

def delete_book(session, book_id: int) -> int:
    """
    Hard-delete a book and its dependent rows.
    Returns number of Book rows deleted (0 or 1).
    """
    # Remove dependents first (since we didn't define ON DELETE CASCADE on FKs)
    session.execute(delete(Review).where(Review.book_id == book_id))
    session.execute(delete(BookAuthor).where(BookAuthor.book_id == book_id))
    # session.execute(delete(BookSubject).where(BookSubject.book_id == book_id))
    res = session.execute(delete(Book).where(Book.id == book_id))
    return res.rowcount or 0

def get_user_review(session, user_id: int, book_id: int) -> Review | None:
    return session.scalar(
        select(Review).where(Review.user_id == user_id, Review.book_id == book_id)
    )

def upsert_review(session, user_id: int, book_id: int, rating: int, text_value: str | None):
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

def delete_user_review(session, user_id: int, book_id: int) -> int:
    res = session.execute(
        delete(Review).where(Review.user_id == user_id, Review.book_id == book_id)
    )
    return res.rowcount or 0

def rating_summary_for_books(session, book_ids: list[int]) -> dict[int, tuple[float, int]]:
    """
    Returns {book_id: (avg_rating, n_reviews)} for the given page of books.
    """
    if not book_ids:
        return {}
    rows = session.execute(
        select(Review.book_id, func.avg(Review.rating), func.count(Review.id))
        .where(Review.book_id.in_(book_ids))
        .group_by(Review.book_id)
    ).all()
    return {bid: (float(avg), int(n)) for bid, avg, n in rows}
