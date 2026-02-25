from __future__ import annotations

import streamlit as st

from core.auth import logout, require_auth
from core.database import get_db
from core.styles import inject_styles

_db = next(get_db())
require_auth(_db)
_db.close()

inject_styles()

name = st.session_state.get("user_name", "there")
st.title(f"Welcome back, {name}!")
st.markdown("Use the sidebar to navigate to your journal, history, or analysis.")

if st.button("Log Out"):
    logout()
    st.rerun()
