import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text
from db import get_session
from dal import top_chonkers_sql, shelf_space_by_user_treemap_sql

def render_analytics_tab():
    st.subheader("📊 Analytics")

    # Top Chonkers (largest by volume)
    st.markdown("### 📦 Top Chonkers (by volume)")
    with get_session() as s:
        df1 = pd.read_sql(top_chonkers_sql(), s.bind)
    if df1.empty:
        st.caption("Add dimensions to some books to see this chart.")
    else:
        fig1 = px.histogram(df1, 
                            x="title", 
                            y="volume_cm3", 
                            text_auto=True)

        fig1.update_layout(xaxis_title="Book Title", 
                           yaxis_title="Volume (cm³)")

        st.plotly_chart(fig1, use_container_width=True)

    st.subheader("🧱 Shelf Space per User (Only for reviewed books)")

    with get_session() as s:
        df3 = pd.read_sql(shelf_space_by_user_treemap_sql(), s.bind)

    if df3.empty or df3["volume_cm3"].isna().all():
        st.caption("No volumes to plot yet. Add dimensions and at least one review per user.")
        return

    fig = px.treemap(
        df3,
        path=["username", "title"],        # ← one rectangle per user, split by book title
        values="volume_cm3",
        hover_data={"volume_cm3": ":.1f"}
    )
    fig.update_layout(margin=dict(t=30, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # Quick totals
    st.caption(
        f"Users: {df3['username'].nunique()} • "
        f"Books (tiles): {len(df3)} • "
        f"Total volume: {df3['volume_cm3'].sum()/1000:.1f} L"
    )

    # Optional: quick debug table
    st.divider()
    st.caption("Recently added (debug)")
    with get_session() as s:
        df = pd.read_sql(text("""
            SELECT id, title, year, height_cm, width_cm, thickness_cm, pages,
                   CASE WHEN height_cm IS NOT NULL AND width_cm IS NOT NULL AND thickness_cm IS NOT NULL
                        THEN (height_cm*width_cm*thickness_cm)/1000.0
                   END AS volume_cm3
            FROM books
            ORDER BY id DESC LIMIT 8
        """), s.bind)
    st.dataframe(df, use_container_width=True)
