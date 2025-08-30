from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import streamlit as st

from db import get_session
from dal import create_book, create_book_from_api
# Adjust this import to your actual package layout:
# if file lives at project_root/openlibrary_client.py, use `from openlibrary_client import ...`
from harvesters.openlibrary_client import search_title, build_payload_from_title_hit


# Cache the lightweight search call for snappy UX
@st.cache_data(show_spinner=False, ttl=60)
def cached_search_title(q: str, limit: int = 12) -> List[Dict[str, Any]]:
    q = (q or "").strip()
    if not q:
        return []
    return search_title(q, limit)


def _normalize_int(v: Any) -> Optional[int]:
    try:
        if v in (None, "", 0):
            return None
        return int(v)
    except Exception:
        return None


def render_add_tab() -> None:
    st.subheader("Add a new book")

    # --- A) Open Library: search by title ---
    st.markdown("### 🔎 Find by Title (Open Library)")

    with st.form("ol_search_form", clear_on_submit=False):
        q = st.text_input("Search a title to prefill", key="ol_q", placeholder="e.g., The Hobbit")
        submitted = st.form_submit_button("Search")
        if submitted:
            q_s = (q or "").strip()
            if q_s:
                with st.spinner("Searching Open Library..."):
                    try:
                        st.session_state["ol_hits"] = cached_search_title(q_s, limit=9) or []
                    except Exception as e:
                        st.session_state["ol_hits"] = []
                        st.error(f"Search failed: {e}")
            else:
                st.session_state["ol_hits"] = []
                st.warning("Enter a title to search.")

    hits: Sequence[Dict[str, Any]] = st.session_state.get("ol_hits", []) or []
    if hits:
        cols = st.columns(3)
        for i, h in enumerate(hits):
            with cols[i % 3]:
                cover = h.get("cover_url")
                if cover:
                    st.image(cover, use_container_width=True)
                st.write(f"**{h.get('title','(no title)')}**")
                authors = h.get("authors") or []
                if authors:
                    st.caption(", ".join(authors))
                year = h.get("year")
                st.caption(f"Year: {year or '—'}")

                # Use external_id to make the key stable across pages
                add_key = f"ol_add_{h.get('external_id', i)}"
                if st.button("Add", key=add_key, use_container_width=True):
                    try:
                        with st.spinner("Fetching edition details & adding…"):
                            payload = build_payload_from_title_hit(h)  # includes dims/pages when available
                            with get_session() as s:
                                book, created = create_book_from_api(s, payload)
                        st.success(("✅ Added" if created else "ℹ️ Already in library") + f": {payload.get('title') or '(no title)'}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Add failed: {e}")
                        st.exception(e)  # full traceback for debugging

    st.divider()

    # --- B) Manual form ---
    st.markdown("### Manual Entry")
    with st.form("add_book_manual"):
        title = st.text_input("Title", placeholder="e.g., Clean Code")

        c_auth, c_year, c_lang = st.columns([2, 1, 1])
        with c_auth:
            authors = st.text_input("Authors (comma-separated)", placeholder="e.g., Robert C. Martin")
        with c_year:
            year = st.number_input("Year", min_value=0, max_value=2100, value=0, step=1)
        with c_lang:
            language = st.text_input("Language (ISO code)", placeholder="en")

        cover_url = st.text_input("Cover URL (optional)", placeholder="https://…")
        description = st.text_area("Description (optional)", placeholder="Short synopsis or notes…")

        st.markdown("**Physical dimensions (optional):**")
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])
        height_cm = c1.number_input("Height (cm)", min_value=0, step=1)
        width_cm = c2.number_input("Width (cm)", min_value=0, step=1)
        thickness_cm = c3.number_input("Thickness (cm)", min_value=0, step=1)
        pages = c4.number_input("Pages", min_value=0, step=1)
        format_sel = c5.selectbox("Format", ["", "paperback", "hardcover", "ebook", "other"], index=0)

        submitted_manual = st.form_submit_button("Add book")
        if submitted_manual:
            if not (title or "").strip():
                st.error("Title is required.")
            else:
                try:
                    with get_session() as s:
                        create_book(
                            s,
                            title=title.strip(),
                            year=_normalize_int(year),
                            description=(description or "").strip() or None,
                            cover_url=(cover_url or "").strip() or None,
                            language=(language or "").strip() or None,
                            authors=[a.strip() for a in (authors or "").split(",") if a.strip()],
                            height_cm=_normalize_int(height_cm),
                            width_cm=_normalize_int(width_cm),
                            thickness_cm=_normalize_int(thickness_cm),
                            pages=_normalize_int(pages),
                            format=(format_sel or "").strip() or None,
                        )
                    st.success(f"Added: {title.strip()}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add book: {e}")
                    st.exception(e)

