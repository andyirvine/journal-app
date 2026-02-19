from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt
import google.auth.transport.requests
import streamlit as st
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from core.database import Session, User

# URL query param that carries the signed session token.
# It survives page refresh because it's part of the URL.
_SESSION_PARAM = "_s"
_SESSION_DAYS = 30


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Email/password auth
# ---------------------------------------------------------------------------

def register_user(db: Session, email: str, password: str, name: str) -> Tuple[bool, str]:
    email = email.strip().lower()
    if not email or not password or not name:
        return False, "All fields are required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return False, "An account with that email already exists."
    user = User(email=email, password_hash=hash_password(password), name=name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return True, "Account created successfully."


def login_user(db: Session, email: str, password: str) -> Tuple[Optional[User], str]:
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None, "No account found with that email."
    if not user.password_hash:
        return None, "This account uses Google Sign-In. Please use the Google button."
    if not verify_password(password, user.password_hash):
        return None, "Incorrect password."
    return user, "Logged in successfully."


# ---------------------------------------------------------------------------
# Signed session token (HMAC-SHA256, stored in URL query param)
# ---------------------------------------------------------------------------

def _secret() -> bytes:
    return os.getenv("APP_SECRET_KEY", "fallback-secret-please-change").encode()


def _make_token(user_id: int) -> str:
    exp = (datetime.utcnow() + timedelta(days=_SESSION_DAYS)).isoformat()
    payload = json.dumps({"uid": user_id, "exp": exp}, separators=(",", ":")).encode()
    sig = hmac.new(_secret(), payload, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload).decode() + "." + sig


def _decode_token(token: str) -> Optional[int]:
    try:
        encoded, sig = token.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(encoded + "==")
        expected = hmac.new(_secret(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(payload)
        if datetime.fromisoformat(data["exp"]) < datetime.utcnow():
            return None
        return int(data["uid"])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def set_session_user(user: User) -> None:
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user.id
    st.session_state["user_name"] = user.name
    st.session_state["user_email"] = user.email


def set_session_param(user_id: int) -> None:
    """Embed a signed token in the URL so it survives page refresh."""
    st.query_params[_SESSION_PARAM] = _make_token(user_id)


def restore_session_from_params(db: Session) -> None:
    """Read the URL token and restore the session. Fully synchronous — no components."""
    if st.session_state.get("authenticated"):
        return
    token = st.query_params.get(_SESSION_PARAM)
    if not token:
        return
    user_id = _decode_token(token)
    if not user_id:
        st.query_params.pop(_SESSION_PARAM, None)
        return
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        set_session_user(user)


def logout() -> None:
    st.query_params.pop(_SESSION_PARAM, None)
    keys = ["authenticated", "user_id", "user_name", "user_email",
            "journal_content", "current_word_count", "selected_history_date",
            "oauth_state", "narrative_observation", "contextual_insight"]
    for k in keys:
        st.session_state.pop(k, None)
    for k in [k for k in st.session_state if k.startswith("balloon_shown_")]:
        st.session_state.pop(k, None)


def require_auth(db: Session) -> None:
    """Ensure the current user is authenticated, restoring from URL token if needed."""
    if st.session_state.get("authenticated"):
        # Re-embed token if navigating to a new page stripped it from the URL.
        if _SESSION_PARAM not in st.query_params:
            set_session_param(st.session_state["user_id"])
        return

    restore_session_from_params(db)

    if not st.session_state.get("authenticated"):
        st.switch_page("app.py")


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

_GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

_REDIRECT_URI = "http://localhost:8501"


def _build_flow() -> Optional[Flow]:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_REDIRECT_URI],
        }
    }
    return Flow.from_client_config(client_config, scopes=_GOOGLE_SCOPES, redirect_uri=_REDIRECT_URI)


def get_google_auth_url() -> Optional[str]:
    flow = _build_flow()
    if not flow:
        return None
    state = secrets.token_urlsafe(16)
    st.session_state["oauth_state"] = state
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
    )
    return auth_url


def handle_google_callback(db: Session, code: str) -> Tuple[Optional[User], str]:
    flow = _build_flow()
    if not flow:
        return None, "Google OAuth is not configured."
    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        request = google.auth.transport.requests.Request()
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            request,
            os.getenv("GOOGLE_CLIENT_ID"),
        )
    except Exception as exc:
        return None, f"Google authentication failed: {exc}"

    google_id = id_info.get("sub")
    email = id_info.get("email", "").lower()
    name = id_info.get("name", email)

    user = db.query(User).filter(User.google_id == google_id).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
            db.commit()
    if not user:
        user = User(email=email, name=name, google_id=google_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    return user, "Logged in with Google."
