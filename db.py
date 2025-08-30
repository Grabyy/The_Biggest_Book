# db.py
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Iterator
import os

def _db_url():
    # Prefer Streamlit secrets if available
    try:
        import streamlit as st  # noqa: WPS433
        url = st.secrets.get("connections", {}).get("sql", {}).get("url")
        if url:
            return url
    except Exception:
        pass
    # Env var fallback
    return os.getenv("DATABASE_URL", "sqlite:///books.db")

DB_URL = _db_url()
engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False,  # critical for Streamlit pattern
)

@contextmanager
def get_session() -> Iterator:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
