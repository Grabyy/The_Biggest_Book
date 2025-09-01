from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from db import get_session, engine
from models import Base, User

from tabs.browse import render_browse_tab
from tabs.add import render_add_tab
from tabs.reviews import render_reviews_tab
from tabs.analytics import render_analytics_tab

# ---------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------
st.set_page_config(page_title="The Biggest Books App", layout="wide")

# ---------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------
col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    st.title("Welcome to The Biggest Books App")
    st.markdown(
        "Add and explore books, write reviews, and analyze your collection with interactive charts. Have fun! :)"
    )

# ---------------------------------------------------------------------
# Ensure tables exist
# ---------------------------------------------------------------------
try:
    Base.metadata.create_all(bind=engine)
except Exception as exc:
    st.error("Failed to initialize database tables.")
    st.exception(exc)
    st.stop()

# ---------------------------------------------------------------------
# Simple username switcher
# ---------------------------------------------------------------------
with st.sidebar:
    st.header("Sign in")
    default_username = st.session_state.get("username", "demo")

    with st.form("username_form", clear_on_submit=False):
        username = st.text_input("Username", value=default_username)
        submitted = st.form_submit_button("Use this username", use_container_width=True)
        if submitted:
            st.session_state["username"] = (username or "demo").strip() or "demo"

current_username = st.session_state.get("username", "demo")

# Ensure user exists in DB and store id in session
with get_session() as s:
    user = s.scalar(select(User).where(User.username == current_username))
    if not user:
        user = User(username=current_username)
        s.add(user)
        s.flush()  # ensures user.id is available
    st.session_state["user_id"] = user.id

# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------
browse_tab, add_tab, my_reviews_tab, analytics_tab = st.tabs(
    ["Browse", "Add Book", "My Reviews", "Analytics"]
)

with browse_tab:
    render_browse_tab()

with add_tab:
    render_add_tab()

with my_reviews_tab:
    render_reviews_tab(current_username)

with analytics_tab:
    render_analytics_tab()

