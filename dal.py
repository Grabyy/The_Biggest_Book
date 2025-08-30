# dal.py
from typing import List, Optional, Tuple
from sqlalchemy import select, func, desc
from sqlalchemy.orm import joinedload
from models import Book, Author, Subject, Review
from sqlalchemy.orm import joinedload
from sqlalchemy import select

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

def _get_or_create_subject(session, name: str) -> Subject:
    name = (name or "").strip()
    if not name:
        return None
    s = session.scalar(select(Subject).where(func.lower(Subject.name) == name.lower()))
    if s:
        return s
    s = Subject(name=name)
    session.add(s)
    session.flush()
    return s

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
    subjects: List[str] = None,
    height_mm: Optional[int] = None,
    width_mm: Optional[int] = None,
    thickness_mm: Optional[int] = None,
    pages: Optional[int] = None,
    format: Optional[str] = None,
):
    authors = authors or []
    subjects = subjects or []
    book = Book(
        title=title.strip(),
        year=year,
        description=(description or None),
        cover_url=(cover_url or None),
        language=(language or None),
        height_mm=height_mm,
        width_mm=width_mm,
        thickness_mm=thickness_mm,
        pages=pages,
        format=(format or None),
    )
    for n in authors:
        a = _get_or_create_author(session, n)
        if a:
            book.authors.append(a)
    for n in subjects:
        s = _get_or_create_subject(session, n)
        if s:
            book.subjects.append(s)
    session.add(book)
    session.flush()
    return book

def update_book_dimensions(session, book_id: int, *, height_mm=None, width_mm=None, thickness_mm=None, pages=None, format=None):
    book = session.get(Book, book_id)
    if not book:
        return None
    if height_mm is not None: book.height_mm = height_mm
    if width_mm is not None: book.width_mm = width_mm
    if thickness_mm is not None: book.thickness_mm = thickness_mm
    if pages is not None: book.pages = pages
    if format is not None: book.format = format
    session.flush()
    return book

# ---------- queries / listing ----------

def list_subjects(session) -> List[Subject]:
    return session.execute(select(Subject).order_by(Subject.name.asc())).scalars().all()

def list_books(
    session,
    *,
    q: Optional[str] = None,
    subject_ids: Optional[List[int]] = None,
    page: int = 1,
) -> Tuple[List[Book], int]:
    stmt = select(Book).options(
        joinedload(Book.authors),
        joinedload(Book.subjects)
    )

    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Book.title).like(like))

    if subject_ids:
        stmt = stmt.join(Book.subjects).where(Subject.id.in_(subject_ids))

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
from sqlalchemy import text
from models import Review

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
        (height_mm*width_mm*thickness_mm)/1000.0 AS volume_cm3
      FROM books
      WHERE height_mm IS NOT NULL AND width_mm IS NOT NULL AND thickness_mm IS NOT NULL
      ORDER BY volume_cm3 DESC
      LIMIT 20
    """)

def pages_vs_volume_sql():
    return text("""
      SELECT
        b.id, b.title, b.pages,
        (b.height_mm*b.width_mm*b.thickness_mm)/1000.0 AS volume_cm3,
        COALESCE(sj.name, 'Unknown') AS subject
      FROM books b
      LEFT JOIN book_subjects bs ON bs.book_id = b.id
      LEFT JOIN subjects sj ON sj.id = bs.subject_id
      WHERE b.pages IS NOT NULL
        AND b.height_mm IS NOT NULL AND b.width_mm IS NOT NULL AND b.thickness_mm IS NOT NULL
    """)

def shelf_space_by_subject_sql():
    # Total shelf space (sum of volumes) per subject
    return text("""
      SELECT
        COALESCE(sj.name, 'Uncategorized') AS subject,
        SUM( (b.height_mm*b.width_mm*b.thickness_mm)/1000.0 ) AS total_volume_cm3,
        COUNT(DISTINCT b.id) AS books_count
      FROM books b
      LEFT JOIN book_subjects bs ON bs.book_id = b.id
      LEFT JOIN subjects sj ON sj.id = bs.subject_id
      WHERE b.height_mm IS NOT NULL AND b.width_mm IS NOT NULL AND b.thickness_mm IS NOT NULL
      GROUP BY subject
      ORDER BY total_volume_cm3 DESC
      LIMIT 15
    """)


from sqlalchemy import select
from models import Book

def find_book_by_external_id(session, external_id: str | None):
    if not external_id:
        return None
    return session.scalar(select(Book).where(Book.external_id == external_id))

def create_book_from_api(session, payload: dict):
    # dedupe by external_id, then (title, year)...
    if payload.get("external_id"):
        existing = find_book_by_external_id(session, payload["external_id"])
        if existing:
            return existing, False

    title = (payload.get("title") or "").strip()
    year = payload.get("year")
    existing = session.scalar(select(Book).where(Book.title == title, Book.year == year))
    if existing:
        # If it already exists but we fetched new dims, you may optionally update them:
        # update_book_dimensions(session, existing.id,
        #     height_mm=payload.get("height_mm"),
        #     width_mm=payload.get("width_mm"),
        #     thickness_mm=payload.get("thickness_mm"),
        #     pages=payload.get("pages"))
        return existing, False

    book = create_book(
        session,
        title=title,
        year=year,
        description=payload.get("description"),
        cover_url=payload.get("cover_url"),
        language=payload.get("language"),
        authors=payload.get("authors") or [],
        subjects=payload.get("subjects") or [],
        # 👇 forward dimensions!
        height_mm=payload.get("height_mm"),
        width_mm=payload.get("width_mm"),
        thickness_mm=payload.get("thickness_mm"),
        pages=payload.get("pages"),
        # format left None here
    )
    if payload.get("external_id"):
        book.external_id = payload["external_id"]
    session.flush()
    return book, True
