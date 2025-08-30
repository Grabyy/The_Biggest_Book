# tabs/analytics.py
import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text
from db import get_session
from dal import top_chonkers_sql, pages_vs_volume_sql, shelf_space_by_subject_sql

def render_analytics_tab():
    st.subheader("📊 Analytics")

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

    # Optional: quick debug table
    st.divider()
    st.caption("Recently added (debug)")
    with get_session() as s:
        df = pd.read_sql(text("""
            SELECT id, title, year, height_mm, width_mm, thickness_mm, pages,
                   CASE WHEN height_mm IS NOT NULL AND width_mm IS NOT NULL AND thickness_mm IS NOT NULL
                        THEN (height_mm*width_mm*thickness_mm)/1000.0
                   END AS volume_cm3
            FROM books
            ORDER BY id DESC LIMIT 8
        """), s.bind)
    st.dataframe(df, use_container_width=True)

