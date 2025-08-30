# tabs/add.py
import streamlit as st
from db import get_session
from dal import create_book, create_book_from_api
from harvesters.openlibrary_client import search_title, build_payload_from_title_hit

@st.cache_data(show_spinner=False, ttl=60)
def cached_search_title(q: str, limit: int = 12):
    return search_title(q, limit)

def render_add_tab():
    st.subheader("Add a new book")

    # --- A) Open Library: search by title ---
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
                        payload = build_payload_from_title_hit(h)  # includes dims/pages when available
                        with get_session() as s:
                            book, created = create_book_from_api(s, payload)
                        st.toast(("✅ Added" if created else "ℹ️ Already in library") + f": {payload['title']}")
                    except Exception as e:
                        st.error(f"Add failed: {e}")
                    st.rerun()

    st.divider()

    # --- B) Manual form ---
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

