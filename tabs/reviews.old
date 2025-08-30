# tabs/reviews.py
import streamlit as st
from sqlalchemy import select
from db import get_session
from models import Book
from dal import upsert_review, list_user_reviews

def render_reviews_tab(current_username: str):
    st.subheader(f"My Reviews — {current_username}")

    # Quick selector for a book to review
    with get_session() as s:
        books = s.execute(select(Book).order_by(Book.title.asc())).scalars().all()
    book_map = {b.title: b.id for b in books}
    if not book_map:
        st.info("No books yet. Add some first in the Add tab.")
        return

    title = st.selectbox("Pick a book to review", list(book_map.keys()))
    rating = st.slider("Rating", 1, 5, 4)
    txt = st.text_area("Review (optional)")

    if st.button("Save review"):
        with get_session() as s:
            upsert_review(s, st.session_state["user_id"], book_map[title], rating, txt or None)
        st.success("Saved review!")
    st.divider()

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

