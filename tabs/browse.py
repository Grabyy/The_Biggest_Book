"""
Browse tab for the Streamlit app.

Notes:
- Intentionally avoids caching so edits/reviews reflect immediately after actions.
- Keeps DAL calls exactly as in the original (no behavioral changes).
- Uses 3-column card grid with inline editors for reviews and dimensions.
"""

import math
import streamlit as st
from db import get_session
from dal import (
    list_books,
    update_book_dimensions,
    PAGE_SIZE,
    delete_book,
    upsert_review,
    get_user_review,
    delete_user_review,
    rating_summary_for_books,
)
import urllib.parse


def render_browse_tab():
    """Render the library browsing UI: search, paginate, edit, and manage books."""
    st.subheader("Browse Library")

    # ------------------------------------------------------------------
    # Search & Pagination controls
    # ------------------------------------------------------------------
    col1, col2 = st.columns(2)
    with col1:
        # Simple case-insensitive title search (handled in DAL)
        q = st.text_input(
            "Search title", placeholder="e.g., The Pragmatic Programmer"
        )
    with col2:
        # Page is 1-based; PAGE_SIZE defined in DAL
        page = st.number_input("Page", min_value=1, step=1, value=1)

    # ------------------------------------------------------------------
    # Load current page of books + aggregated rating summaries
    # - rating_summary_for_books returns {book_id: (avg, count)}
    # - Avoids N+1 by aggregating for visible items
    # ------------------------------------------------------------------
    with get_session() as s:
        books, total = list_books(s, q=q, page=page)
        summaries = rating_summary_for_books(s, [b.id for b in books])

    st.caption(f"Total books: {total}")
    total_pages = max(1, math.ceil(total / PAGE_SIZE))

    # 3-column grid for book cards
    cols = st.columns(3, gap="large")

    for i, b in enumerate(books):
        with cols[i % 3]:
            # ----------------------------------------------------------
            # Cover image (if available)
            # ----------------------------------------------------------
            if b.cover_url:
                st.image(b.cover_url, use_container_width=True, caption=b.title)

            # ----------------------------------------------------------
            # Title link
            # - If external_id is set, link to Open Library (books path)
            # - Otherwise, fallback to a Google search for the title
            # ----------------------------------------------------------
            if b.external_id:
                # external_id usually looks like "/books/OL123M" or "/works/OL123W"
                olid = b.external_id.split("/")[-1]
                ol_url = f"https://openlibrary.org/books/{olid}"
                st.markdown(f"### [{b.title}]({ol_url})")
            else:
                query = urllib.parse.quote_plus(b.title)
                gb_url = f"https://www.google.com/search?q={query}"
                st.markdown(f"### [{b.title}]({gb_url})")

            # Authors list (or placeholder)
            st.caption(", ".join(a.name for a in b.authors) or "Unknown author")

            # ----------------------------------------------------------
            # Small rating badge under title (avg + count)
            # ----------------------------------------------------------
            avg, n = summaries.get(b.id, (None, 0))
            if avg is not None:
                st.caption(f"⭐ {avg:.1f} ({n})")
            else:
                st.caption("No ratings yet")

            # ----------------------------------------------------------
            # Review editor (inline)
            # - Prefill with the current user's existing review (if any)
            # - Save or delete triggers rerun to reflect state
            # ----------------------------------------------------------
            with st.expander("⭐ Rate / Review"):
                with get_session() as s:
                    existing = get_user_review(
                        s, st.session_state["user_id"], b.id
                    )

                default_rating = existing.rating if existing else 4
                default_text = existing.text if (existing and existing.text) else ""

                rating = st.slider(
                    f"Your rating for {b.title}",
                    1,
                    5,
                    default_rating,
                    key=f"rate_{b.id}",
                )
                text = st.text_area(
                    "Review (optional)",
                    value=default_text,
                    key=f"rev_{b.id}",
                )

                c1, c2 = st.columns([1, 1])

                # Save review (upsert)
                if c1.button("Save review", key=f"save_rev_{b.id}"):
                    try:
                        with get_session() as s:
                            upsert_review(
                                s,
                                st.session_state["user_id"],
                                b.id,
                                rating,
                                text or None,
                            )
                        st.success("Saved review!")
                    except Exception as e:
                        st.error(f"Could not save review: {e}")
                    # Rerun to refresh the card UI with latest values
                    st.cache_data.clear()  # invalidate cached analytics/data loaders
                    st.rerun()

                # Optional: delete your own review (if present)
                if existing and c2.button(
                    "Delete my review", key=f"del_rev_{b.id}"
                ):
                    try:
                        with get_session() as s:
                            delete_user_review(
                                s, st.session_state["user_id"], b.id
                            )
                        st.success("Deleted your review.")
                    except Exception as e:
                        st.error(f"Delete failed: {e}")
                    st.cache_data.clear()  # invalidate cached analytics/data loaders
                    st.rerun()

            # ----------------------------------------------------------
            # Dimensions editor
            # - Allows editing of physical dimensions & pages
            # - Displays computed volume when all dims are present
            # ----------------------------------------------------------
            with st.expander("Dimensions / Edit"):
                c1, c2, c3 = st.columns(3)
                height = c1.number_input(
                    f"Height cm (#{b.id})",
                    min_value=0,
                    value=b.height_cm or 0,
                    step=1,
                )
                width = c2.number_input(
                    f"Width cm (#{b.id})",
                    min_value=0,
                    value=b.width_cm or 0,
                    step=1,
                )
                thick = c3.number_input(
                    f"Thickness cm (#{b.id})",
                    min_value=0,
                    value=b.thickness_cm or 0,
                    step=1,
                )
                c4, c5 = st.columns(2)
                pages = c4.number_input(
                    f"Pages (#{b.id})", min_value=0, value=b.pages or 0, step=1
                )
                fmt = c5.selectbox(
                    f"Format (#{b.id})",
                    ["", "paperback", "hardcover", "ebook", "other"],
                    index=0
                    if not b.format
                    else ["", "paperback", "hardcover", "ebook", "other"].index(
                        b.format
                    ),
                )

                # Persist dimension edits
                if st.button("Save dims", key=f"save_dims_{b.id}"):
                    with get_session() as s:
                        update_book_dimensions(
                            s,
                            b.id,
                            height_cm=height or None,
                            width_cm=width or None,
                            thickness_cm=thick or None,
                            pages=pages or None,
                            format=fmt or None,
                        )
                    st.success("Saved dimensions!")
                    st.cache_data.clear()  # invalidate cached analytics/data loaders
                    st.rerun()

                # Show computed volume (cm³) when all dims are present
                if all([height, width, thick]):
                    vol = (height * width * thick) / 1000.0
                    st.write(f"**Volume:** {vol:.1f} cm³")

            # ----------------------------------------------------------
            # 🗑️ Danger zone: Hard delete book (+ dependents)
            # - Removes Book, Reviews, and Author links (no cascade in DB)
            # ----------------------------------------------------------
            with st.expander("🗑️ Danger zone"):
                st.caption(
                    "This permanently removes the book, its reviews, and links "
                    "to authors."
                )
                col_del1, col_del2 = st.columns([1, 1])
                confirm_key = f"confirm_del_{b.id}"
                if col_del1.checkbox(
                    "I understand — delete this book", key=confirm_key
                ):
                    if col_del2.button(
                        "Delete permanently", key=f"do_del_{b.id}"
                    ):
                        try:
                            with get_session() as s:
                                n = delete_book(s, b.id)
                            if n:
                                st.success(f"Deleted: {b.title}")
                            else:
                                st.warning(
                                    "Nothing deleted (book may already be gone)."
                                )
                        except Exception as e:
                            st.error(f"Delete failed: {e}")
                        st.cache_data.clear()  # invalidate cached analytics/data loaders
                        st.rerun()

    # ------------------------------------------------------------------
    # Pagination footer
    # ------------------------------------------------------------------
    st.write(f"Page {page} / {total_pages}")

