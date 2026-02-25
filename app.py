import os

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from core.database import get_db, init_db
from core.styles import inject_styles
from core.auth import (
    get_google_auth_url,
    handle_google_callback,
    login_user,
    register_user,
    restore_session_from_params,
    set_session_param,
    set_session_user,
)

st.set_page_config(
    page_title="Morning Journal",
    page_icon="📓",
    layout="wide",
)

init_db()

# ---------------------------------------------------------------------------
# Google OAuth callback — must be handled before anything else
# ---------------------------------------------------------------------------
_oauth_code = st.query_params.get("code")
if _oauth_code:
    for _k in ["code", "state", "scope"]:
        st.query_params.pop(_k, None)
    _db = next(get_db())
    _user, _msg = handle_google_callback(_db, _oauth_code)
    _db.close()
    if _user:
        set_session_user(_user)
        set_session_param(_user.id)
        st.rerun()
    else:
        st.session_state["_oauth_error"] = _msg

# ---------------------------------------------------------------------------
# Restore session from URL token
# ---------------------------------------------------------------------------
if not st.session_state.get("authenticated"):
    _db = next(get_db())
    restore_session_from_params(_db)
    _db.close()

if "_oauth_error" in st.session_state:
    st.error(st.session_state.pop("_oauth_error"))

# ---------------------------------------------------------------------------
# Login / Register UI (shown when not authenticated)
# ---------------------------------------------------------------------------
if not st.session_state.get("authenticated"):
    inject_styles()
    st.title("Morning Journal")
    st.markdown("Write 750 words every day.")

    tab_login, tab_register = st.tabs(["Log In", "Create Account"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In")
        if submitted:
            _db = next(get_db())
            user, msg = login_user(_db, email, password)
            _db.close()
            if user:
                set_session_user(user)
                set_session_param(user.id)
                st.rerun()
            else:
                st.error(msg)

        google_url = get_google_auth_url()
        if google_url:
            st.divider()
            st.link_button("Sign in with Google", google_url, use_container_width=True)
        elif os.getenv("GOOGLE_CLIENT_ID"):
            st.info("Google OAuth is partially configured — check GOOGLE_CLIENT_SECRET.")

    with tab_register:
        with st.form("register_form"):
            reg_name = st.text_input("Name")
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password (min 8 chars)", type="password", key="reg_pw")
            reg_confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")
            reg_submitted = st.form_submit_button("Create Account")
        if reg_submitted:
            if reg_password != reg_confirm:
                st.error("Passwords do not match.")
            else:
                _db = next(get_db())
                ok, msg = register_user(_db, reg_email, reg_password, reg_name)
                _db.close()
                if ok:
                    st.success(msg + " You can now log in.")
                else:
                    st.error(msg)

    st.stop()

# ---------------------------------------------------------------------------
# Authenticated navigation
# ---------------------------------------------------------------------------
pg = st.navigation(
    {
        "": [
            st.Page("pages/1_Journal.py", title="Journal"),
            st.Page("pages/2_History.py", title="History"),
            st.Page("pages/3_Analysis.py", title="Analysis & Insights"),
            st.Page("pages/4_Import.py", title="Import"),
            st.Page("pages/5_Chat.py", title="Ask Your Journal"),
        ],
        " ": [
            st.Page("pages/account.py", title="Account"),
        ],
    }
)
pg.run()
