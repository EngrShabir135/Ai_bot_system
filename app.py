"""United Union Bank - AI Command Bot System for Unified Investment Portfolio Management.

Run locally:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="United Union Bank",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

import db # noqa: E402
import auth_view
import pages
import styles  # noqa: E402


@st.cache_resource
def _init() -> bool:
    db.init_db()
    return True


_init()
styles.inject()

if st.session_state.get("user") is None:
    auth_view.render()
else:
    pages.render()
