"""
Reviews tab for the Streamlit app.

Notes:
- Behavior intentionally unchanged: same queries and UI flow.
- Users pick a book, rate it, optionally add text, and save via DAL's upsert.
- Recent reviews are shown below, newest first (as provided by DAL).
"""

import streamlit as st
from sqlalchemy import select

from db import get_session
from models import Book
from dal import upsert_review, list_user_reviews


def render_reviews_tab(current_username: str):
    """Render the 'My Reviews' tab for the given display username."""
    st.subheader(f"My Reviews — {current_username}")

    # ------------------------------------------------------------------
    # Quick selector for a book to review
    # - Load all books alphabetically for the dropdown
    # - If none exist, prompt the user to add some first
    # ------------------------------------------------------------------
    with get_session() as s:
        books = (
            s.execute(select(Book).order_by(Book.title.asc()))
            .scalars()
            .all()
        )

    book_map = {b.title: b.id for b in books}
    if not book_map:
        st.info("No books yet. Add some first in the Add tab.")
        return

    # Inputs for creating/updating a review (one per user per book)
    title = st.selectbox("Pick a book to review", list(book_map.keys()))
    rating = st.slider("Rating", 1, 5, 4)
    txt = st.text_area("Review (optional)")

    # Persist review to DB (upsert)
    if st.button("Save review"):
        with get_session() as s:
            upsert_review(
                s,
                st.session_state["user_id"],
                book_map[title],
                rating,
                txt or None,
            )
        st.success("Saved review!")
    
    st.cache_data.clear()  # invalidate cached analytics/data loaders

    st.divider()

    # ------------------------------------------------------------------
    # Your recent reviews (as provided by DAL: newest first)
    # ------------------------------------------------------------------
    st.markdown("### Your recent reviews")
    with get_session() as s:
        rows = list_user_reviews(s, st.session_state["user_id"])

    if not rows:
        st.caption("No reviews yet.")
    else:
        for r in rows:
            st.markdown(f"**{r.book.title}** — {r.rating}/5")
            if r.text:
                st.write(r.text)
            st.caption(r.created_at.strftime("%Y-%m-%d %H:%M"))

