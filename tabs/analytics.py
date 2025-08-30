# tabs/analytics.py
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from db import get_session
from dal import top_chonkers_sql, shelf_space_by_user_treemap_sql


# ----------------------------
# Cached data loaders
# ----------------------------
@st.cache_data(show_spinner=False, ttl=60)
def _load_top_chonkers_df() -> pd.DataFrame:
    with get_session() as s:
        # pandas accepts an Engine/Connection; s.bind is the Engine
        df = pd.read_sql(top_chonkers_sql(), s.bind)
    # Ensure numeric dtype
    if "volume_cm3" in df.columns:
        df["volume_cm3"] = pd.to_numeric(df["volume_cm3"], errors="coerce")
    return df


@st.cache_data(show_spinner=False, ttl=60)
def _load_shelf_space_df() -> pd.DataFrame:
    with get_session() as s:
        df = pd.read_sql(shelf_space_by_user_treemap_sql(), s.bind)
    for col in ("volume_cm3",):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(show_spinner=False, ttl=60)
def _load_recent_books_df(limit: int = 8) -> pd.DataFrame:
    with get_session() as s:
        df = pd.read_sql(
            text(
                f"""
                SELECT id, title, year, height_cm, width_cm, thickness_cm, pages,
                       CASE
                         WHEN height_cm IS NOT NULL AND width_cm IS NOT NULL AND thickness_cm IS NOT NULL
                         THEN (height_cm*width_cm*thickness_cm)/1000.0
                       END AS volume_cm3
                FROM books
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            s.bind,
            params={"limit": int(limit)},
        )
    return df


# ----------------------------
# Renderer
# ----------------------------
def render_analytics_tab() -> None:
    st.subheader("Analytics")

    # ---- Top Chonkers (largest by volume)
    st.markdown("### Top Chonkers (by volume)")
    df1 = _load_top_chonkers_df()
    if df1.empty or df1["volume_cm3"].fillna(0).le(0).all():
        st.caption("Add height, width, and thickness to some books to see this chart.")
    else:
        # Bar chart (sorted by volume desc)
        df1_sorted = df1.sort_values("volume_cm3", ascending=False)
        fig1 = px.bar(
            df1_sorted,
            x="title",
            y="volume_cm3",
            text="volume_cm3",
        )
        fig1.update_layout(
            xaxis_title="Book Title",
            yaxis_title="Volume (cm³)",
        )
        st.plotly_chart(fig1, use_container_width=True)

    # ---- Shelf space per user (treemap)
    st.markdown("### Shelf Space per User (only for reviewed books)")
    df3 = _load_shelf_space_df()

    if df3.empty or df3["volume_cm3"].isna().all() or df3["volume_cm3"].fillna(0).le(0).all():
        st.caption("No volumes to plot yet. Add dimensions and at least one review per user.")
    else:
        fig = px.treemap(
            df3,
            path=["username", "title"],  # one rectangle per user, split by book title
            values="volume_cm3",
            hover_data={"volume_cm3": ":.1f"},
        )
        fig.update_layout(margin=dict(t=30, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # Quick totals
        total_liters = (df3["volume_cm3"].fillna(0).sum() / 1000.0)
        st.caption(
            f"Users: {df3['username'].nunique()} • "
            f"Books (tiles): {len(df3)} • "
            f"Total volume: {total_liters:.1f} L"
        )

    # ---- Optional debug table
    with st.expander("Recently added (debug)", expanded=False):
        df_recent = _load_recent_books_df(limit=8)
        st.dataframe(df_recent, use_container_width=True)

