import streamlit as st
from sqlalchemy import select
from db import get_session, engine
from models import Base, User

# Tab renderers
from tabs.browse import render_browse_tab
from tabs.add import render_add_tab
from tabs.reviews import render_reviews_tab
from tabs.analytics import render_analytics_tab

st.set_page_config(page_title="The Biggest Books App", layout="wide")

col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    st.title("Welcome to The biggest Books App")
    st.markdown("Add and explore books, write reviews, and analyze your collection with interactive charts, have fun :)")


# Ensure tables exist
Base.metadata.create_all(bind=engine)

# --- Simple username switcher (demo auth) ---
st.sidebar.header("Sign in")
username = st.sidebar.text_input("Username", value="demo")
if st.sidebar.button("Use this username", use_container_width=True):
    st.session_state["username"] = username or "demo"
current_username = st.session_state.get("username", "demo")

# Ensure user exists in DB and store id in session
with get_session() as s:
    u = s.scalar(select(User).where(User.username == current_username))
    if not u:
        u = User(username=current_username)
        s.add(u)
        s.flush()
    st.session_state["user_id"] = u.id

# --- Tabs ---
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

