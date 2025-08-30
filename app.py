# app.py
import math
import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import select

from db import get_session, engine
from models import Base, User, Subject
from dal import (
    # listing + CRUD
    list_books, list_subjects, create_book, update_book_dimensions, PAGE_SIZE,
    # reviews
    upsert_review, list_user_reviews,
    # analytics queries
    top_chonkers_sql, pages_vs_volume_sql, shelf_space_by_subject_sql,
    # API-based creation
    create_book_from_api
)

from harvesters.openlibrary_client import search_title, build_payload_from_title_hit

# ---------- Streamlit page config ----------
st.set_page_config(page_title="📚 Books App", layout="wide")
st.title("📚 Books App — Streamlit + SQL (No ML)")

# Ensure tables exist (safe no-op if already created)
Base.metadata.create_all(bind=engine)

# ---------- Simple demo "login" (username only) ----------
st.sidebar.header("Sign in")
username = st.sidebar.text_input("Username", value="demo")
if st.sidebar.button("Use this username", use_container_width=True):
    st.session_state["username"] = username or "demo"
current_username = st.session_state.get("username", "demo")

# Ensure user exists
with get_session() as s:
    u = s.scalar(select(User).where(User.username == current_username))
    if not u:
        u = User(username=current_username)
        s.add(u)
        s.flush()
    st.session_state["user_id"] = u.id

# ---------- Cached API wrappers ----------
@st.cache_data(show_spinner=False, ttl=60)
def cached_search_title(q: str, limit: int = 12):
    return search_title(q, limit)

# ---------- Tabs ----------
browse_tab, add_tab, my_reviews_tab, analytics_tab = st.tabs(
    ["Browse", "Add Book", "My Reviews", "Analytics"]
)

# ========================= Browse Tab =========================
with browse_tab:
    st.subheader("Browse Library")

    col1, col2, col3 = st.columns([3, 3, 1])
    with col1:
        q = st.text_input("Search title", placeholder="e.g., The Pragmatic Programmer")
    with col2:
        with get_session() as s:
            subs = list_subjects(s)
        subject_options = {sub.name: sub.id for sub in subs}
        chosen = st.multiselect("Filter by subjects", list(subject_options.keys()))
        subject_ids = [subject_options[c] for c in chosen] if chosen else None
    with col3:
        page = st.number_input("Page", min_value=1, step=1, value=1)

    with get_session() as s:
        books, total = list_books(s, q=q, subject_ids=subject_ids, page=page)

    st.caption(f"Total books: {total}")
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    cols = st.columns(3)

    for i, b in enumerate(books):
        with cols[i % 3]:
            if b.cover_url:
                st.image(b.cover_url, use_container_width=True, caption=b.title)
            st.markdown(f"### {b.title}")
            st.caption(", ".join(a.name for a in b.authors) or "Unknown author")
            if b.subjects:
                st.write("**Subjects:** " + ", ".join(sj.name for sj in b.subjects))

            # Reviews (one per user)
            with st.expander("⭐ Rate / Review"):
                rating = st.slider(f"Rating for {b.title}", 1, 5, 4, key=f"rate_{b.id}")
                txt = st.text_area("Review (optional)", key=f"txt_{b.id}")
                if st.button("Save review", key=f"save_rev_{b.id}"):
                    with get_session() as s:
                        upsert_review(s, st.session_state["user_id"], b.id, rating, txt or None)
                    st.success("Saved review!")

            # Dimensions editor
            with st.expander("📏 Dimensions / Edit"):
                c1, c2, c3 = st.columns(3)
                height = c1.number_input(f"Height mm (#{b.id})", min_value=0, value=b.height_mm or 0, step=1)
                width  = c2.number_input(f"Width mm (#{b.id})", min_value=0, value=b.width_mm or 0, step=1)
                thick  = c3.number_input(f"Thickness mm (#{b.id})", min_value=0, value=b.thickness_mm or 0, step=1)
                c4, c5 = st.columns(2)
                pages  = c4.number_input(f"Pages (#{b.id})", min_value=0, value=b.pages or 0, step=1)
                fmt    = c5.selectbox(
                    f"Format (#{b.id})",
                    ["", "paperback", "hardcover", "ebook", "other"],
                    index=0 if not b.format else ["","paperback","hardcover","ebook","other"].index(b.format)
                )
                if st.button("Save dims", key=f"save_dims_{b.id}"):
                    with get_session() as s:
                        update_book_dimensions(s, b.id,
                            height_mm=height or None,
                            width_mm=width or None,
                            thickness_mm=thick or None,
                            pages=pages or None,
                            format=fmt or None
                        )
                    st.success("Saved dimensions!")
                if all([height, width, thick]):
                    vol = (height * width * thick) / 1000.0
                    st.write(f"**Volume:** {vol:.1f} cm³")

    st.write(f"Page {page} / {total_pages}")

with add_tab:
    st.subheader("Add a new book")

    # ---------- A) Open Library: search by title ----------
    st.markdown("### 🔎 Find by Title (Open Library)")
    q = st.text_input("Search a title to prefill", key="ol_q", placeholder="e.g., The Hobbit")

    if st.button("Search", key="ol_search_btn"):
        q_s = (q or "").strip()
        if q_s:
            st.session_state["ol_hits"] = cached_search_title(q_s, limit=9) or []
        else:
            st.session_state["ol_hits"] = []
            st.warning("Enter a title to search.")

    hits = st.session_state.get("ol_hits", [])
    if hits:
        cols = st.columns(3)
        for i, h in enumerate(hits):
            with cols[i % 3]:
                if h.get("cover_url"):
                    st.image(h["cover_url"], use_container_width=True)
                st.write(f"**{h.get('title','(no title)')}**")
                if h.get("authors"):
                    st.caption(", ".join(h["authors"]))
                year = h.get("year")
                st.caption(f"Year: {year or '—'}")

                if st.button("Add", key=f"ol_add_{i}"):
                    try:
                        # Build enriched payload with dimensions/pages
                        payload = build_payload_from_title_hit(h)
                        with get_session() as s:
                            book, created = create_book_from_api(s, payload)
                        st.toast(("✅ Added" if created else "ℹ️ Already in library") + f": {payload['title']}")
                    except Exception as e:
                        st.error(f"Add failed: {e}")
                    st.rerun()

    st.divider()

    # ---------- B) Manual form ----------
    st.markdown("### 📝 Manual Entry")
    with st.form("add_book_manual"):
        title = st.text_input("Title", placeholder="e.g., Clean Code")
        authors = st.text_input("Authors (comma-separated)", placeholder="e.g., Robert C. Martin")
        subjects = st.text_input("Subjects (comma-separated)", placeholder="e.g., Software, Best practices")
        year = st.number_input("Year", min_value=0, max_value=2100, value=0, step=1)
        language = st.text_input("Language (ISO code)", placeholder="en")
        cover_url = st.text_input("Cover URL (optional)", placeholder="https://...")
        description = st.text_area("Description (optional)")
        st.markdown("**Physical dimensions (optional):**")
        c1, c2, c3, c4 = st.columns(4)
        height_mm = c1.number_input("Height (mm)", min_value=0, step=1)
        width_mm = c2.number_input("Width (mm)", min_value=0, step=1)
        thickness_mm = c3.number_input("Thickness (mm)", min_value=0, step=1)
        pages = c4.number_input("Pages", min_value=0, step=1)
        format_sel = st.selectbox("Format", ["", "paperback", "hardcover", "ebook", "other"], index=0)

        submitted = st.form_submit_button("Add book")
        if submitted:
            if not title.strip():
                st.error("Title is required.")
            else:
                try:
                    with get_session() as s:
                        create_book(
                            s,
                            title=title.strip(),
                            year=int(year) if year else None,
                            description=description.strip() or None,
                            cover_url=cover_url.strip() or None,
                            language=language.strip() or None,
                            authors=[a.strip() for a in authors.split(",") if a.strip()],
                            subjects=[g.strip() for g in subjects.split(",") if g.strip()],
                            height_mm=height_mm or None,
                            width_mm=width_mm or None,
                            thickness_mm=thickness_mm or None,
                            pages=pages or None,
                            format=format_sel or None,
                        )
                    st.toast(f"✅ Added: {title}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add book: {e}")

# ========================= My Reviews Tab =========================
with my_reviews_tab:
    st.subheader(f"My Reviews — {current_username}")
    with get_session() as s:
        rows = list_user_reviews(s, st.session_state["user_id"])
    if not rows:
        st.info("No reviews yet. Add one from the Browse tab.")
    else:
        for r in rows:
            st.markdown(f"**{r.book.title}** — {r.rating}/5")
            if r.text:
                st.write(r.text)
            st.caption(r.created_at.strftime("%Y-%m-%d %H:%M"))

# ========================= Analytics Tab =========================
with analytics_tab:
    st.subheader("Analytics")

    # Top Chonkers (largest by volume)
    st.markdown("### 📦 Top Chonkers (by volume)")
    with get_session() as s:
        df1 = pd.read_sql(top_chonkers_sql(), s.bind)
    if df1.empty:
        st.caption("Add dimensions to some books to see this chart.")
    else:
        fig1 = px.bar(df1, x="title", y="volume_cm3")
        st.plotly_chart(fig1, use_container_width=True)

    # Pages vs Volume bubble, color by subject
    st.markdown("### 📖 Pages vs Volume")
    with get_session() as s:
        df2 = pd.read_sql(pages_vs_volume_sql(), s.bind)
    if df2.empty:
        st.caption("Need pages and dimensions to plot this.")
    else:
        fig2 = px.scatter(
            df2, x="volume_cm3", y="pages", size="volume_cm3",
            hover_name="title", color="subject"
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Shelf space by subject
    st.markdown("### 🗂️ Shelf Space by Subject")
    with get_session() as s:
        df3 = pd.read_sql(shelf_space_by_subject_sql(), s.bind)
    if df3.empty:
        st.caption("Once you have dimensions + subjects, this fills in.")
    else:
        fig3 = px.bar(df3, x="subject", y="total_volume_cm3", hover_data=["books_count"])
        st.plotly_chart(fig3, use_container_width=True)

