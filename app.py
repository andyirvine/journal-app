import base64
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

    # ── Marketing page styles ────────────────────────────────────────────────
    st.markdown("""
    <style>
    .hero-title {
        font-size: 2.6rem !important;
        font-weight: 800 !important;
        line-height: 1.15 !important;
        margin: 0.5rem 0 0.85rem !important;
        color: #1A1A2E !important;
        letter-spacing: -0.5px;
    }
    .hero-tagline {
        font-size: 1.08rem;
        color: #55546A;
        margin-bottom: 2.2rem;
        line-height: 1.7;
    }
    .section-label {
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #7C6FAF;
        margin-bottom: 0.9rem;
    }
    .benefit-cards {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.8rem;
        margin-bottom: 2rem;
    }
    .benefit-card {
        background: #F5F2FF;
        border-radius: 14px;
        padding: 1.1rem 1rem;
    }
    .benefit-card .b-icon { font-size: 1.5rem; margin-bottom: 0.4rem; }
    .benefit-card .b-title {
        font-weight: 700;
        font-size: 0.87rem;
        color: #1A1A2E;
        margin-bottom: 0.25rem;
    }
    .benefit-card .b-body { font-size: 0.79rem; color: #666; line-height: 1.55; }
    .feature-items { display: flex; flex-direction: column; gap: 0.5rem; }
    .feature-item {
        font-size: 0.88rem;
        color: #3D3A50;
        padding: 0.55rem 0.9rem;
        background: #FAFAFA;
        border-radius: 8px;
        border-left: 3px solid #7C6FAF;
        line-height: 1.5;
    }
    </style>
    """, unsafe_allow_html=True)

    HERO_SVG = """
    <svg viewBox="0 0 420 340" xmlns="http://www.w3.org/2000/svg"
         style="width:100%;max-width:400px;display:block;margin:0 auto">
      <!-- Warm background circle -->
      <circle cx="210" cy="175" r="155" fill="#FBF6EE"/>
      <!-- Purple accent blob top-right -->
      <circle cx="318" cy="82" r="58" fill="#EDE8F7" opacity="0.65"/>
      <!-- Blue accent blob bottom-left -->
      <circle cx="90" cy="265" r="42" fill="#E8F4FD" opacity="0.55"/>

      <!-- Desk surface -->
      <rect x="50" y="266" width="320" height="14" rx="7" fill="#CDB99A"/>
      <rect x="50" y="279" width="320" height="5" rx="2.5" fill="#B8A27E"/>

      <!-- Journal shadow -->
      <ellipse cx="210" cy="275" rx="128" ry="10" fill="#C4AA88" opacity="0.25"/>

      <!-- Open journal — left page -->
      <path d="M82 202 L205 195 L205 267 L80 273 Z"
            fill="#FEFDF8" stroke="#DDD0B3" stroke-width="1.5" stroke-linejoin="round"/>
      <!-- Open journal — right page -->
      <path d="M209 195 L338 202 L340 273 L209 267 Z"
            fill="#FEFDF8" stroke="#DDD0B3" stroke-width="1.5" stroke-linejoin="round"/>
      <!-- Spine -->
      <rect x="204" y="195" width="5" height="72" fill="#DDD0B3"/>

      <!-- Ruled lines — left page -->
      <line x1="97"  y1="216" x2="193" y2="213" stroke="#E8DEC4" stroke-width="1.5" stroke-linecap="round"/>
      <line x1="95"  y1="229" x2="191" y2="226" stroke="#E8DEC4" stroke-width="1.5" stroke-linecap="round"/>
      <line x1="93"  y1="242" x2="189" y2="239" stroke="#E8DEC4" stroke-width="1.5" stroke-linecap="round"/>
      <line x1="91"  y1="255" x2="155" y2="253" stroke="#E8DEC4" stroke-width="1.5" stroke-linecap="round"/>

      <!-- Ruled lines — right page (active writing) -->
      <line x1="221" y1="213" x2="323" y2="216" stroke="#E8DEC4" stroke-width="1.5" stroke-linecap="round"/>
      <line x1="223" y1="226" x2="325" y2="229" stroke="#E8DEC4" stroke-width="1.5" stroke-linecap="round"/>
      <line x1="224" y1="239" x2="282" y2="242" stroke="#9D8FCC" stroke-width="1.5" stroke-linecap="round" opacity="0.6"/>
      <!-- Blinking cursor -->
      <rect x="284" y="236" width="2.5" height="11" rx="1" fill="#5C4B8A"/>

      <!-- ── Person (abstract geometric) ── -->
      <!-- Chair back legs (subtle) -->
      <rect x="176" y="178" width="8" height="78" rx="4" fill="#A0896A" opacity="0.35"/>
      <rect x="236" y="178" width="8" height="78" rx="4" fill="#A0896A" opacity="0.35"/>
      <rect x="176" y="178" width="68" height="8" rx="4" fill="#A0896A" opacity="0.35"/>

      <!-- Torso / sweater -->
      <path d="M176 212 Q210 200 244 212 L252 264 Q210 272 168 264 Z" fill="#6B5B9A"/>

      <!-- Neck -->
      <rect x="201" y="192" width="18" height="16" rx="6" fill="#F2BC98"/>

      <!-- Head -->
      <ellipse cx="210" cy="158" rx="31" ry="34" fill="#F2BC98"/>

      <!-- Hair -->
      <path d="M179 155 Q179 118 210 114 Q241 118 241 155 Q231 134 210 136 Q189 134 179 155Z"
            fill="#2C1A0E"/>

      <!-- Ear -->
      <ellipse cx="179" cy="160" rx="5.5" ry="7" fill="#EDAA82"/>

      <!-- Glasses -->
      <circle cx="198" cy="160" r="9.5" fill="none" stroke="#2C1A0E" stroke-width="1.4" opacity="0.25"/>
      <circle cx="222" cy="160" r="9.5" fill="none" stroke="#2C1A0E" stroke-width="1.4" opacity="0.25"/>
      <line x1="207.5" y1="160" x2="212.5" y2="160" stroke="#2C1A0E" stroke-width="1.4" opacity="0.25"/>
      <line x1="188.5" y1="159" x2="179"   y2="157" stroke="#2C1A0E" stroke-width="1.4" opacity="0.25"/>
      <line x1="231.5" y1="159" x2="241"   y2="157" stroke="#2C1A0E" stroke-width="1.4" opacity="0.25"/>

      <!-- Left arm (writing) -->
      <path d="M176 224 Q154 248 150 268"
            stroke="#6B5B9A" stroke-width="17" stroke-linecap="round" fill="none"/>
      <!-- Left hand -->
      <ellipse cx="150" cy="272" rx="9" ry="7" fill="#F2BC98" transform="rotate(-15 150 272)"/>
      <!-- Pen -->
      <line x1="155" y1="264" x2="188" y2="244"
            stroke="#1A1010" stroke-width="2.5" stroke-linecap="round"/>
      <polygon points="188,242 194,238 193,246" fill="#E53935"/>
      <rect x="158" y="260" width="5" height="5" rx="1" fill="#E8D44D"
            transform="rotate(-35 160 262)"/>

      <!-- Right arm (resting) -->
      <path d="M244 224 Q266 248 270 265"
            stroke="#6B5B9A" stroke-width="17" stroke-linecap="round" fill="none"/>
      <!-- Right hand -->
      <ellipse cx="270" cy="269" rx="9" ry="7" fill="#F2BC98" transform="rotate(15 270 269)"/>

      <!-- ── Thought bubbles (ideas flowing) ── -->
      <circle cx="278" cy="115" r="18" fill="#EDE8F7" opacity="0.75"/>
      <circle cx="300" cy="95"  r="12" fill="#EDE8F7" opacity="0.55"/>
      <circle cx="314" cy="80"  r="7"  fill="#EDE8F7" opacity="0.38"/>

      <!-- ── Sparkles / decorative dots ── -->
      <!-- 4-pointed star top-left -->
      <path d="M72 110 L75.5 99 L79 110 L90 113.5 L79 117 L75.5 128 L72 117 L61 113.5 Z"
            fill="#F6C90E" opacity="0.75"/>
      <!-- Small star right -->
      <path d="M346 160 L348 153 L350 160 L357 162 L350 164 L348 171 L346 164 L339 162 Z"
            fill="#F6C90E" opacity="0.55"/>
      <!-- Dots -->
      <circle cx="55"  cy="195" r="4.5" fill="#90CAF9" opacity="0.6"/>
      <circle cx="358" cy="232" r="3.5" fill="#90CAF9" opacity="0.5"/>
      <circle cx="355" cy="100" r="4"   fill="#A8D5A2" opacity="0.6"/>
      <circle cx="58"  cy="242" r="3"   fill="#A8D5A2" opacity="0.5"/>
    </svg>
    """

    col_left, col_right = st.columns([57, 43], gap="large")

    # ── Left: marketing content ──────────────────────────────────────────────
    with col_left:
        # Each st.markdown call must start with the opening tag on the first
        # line — otherwise Markdown's 4-space-indent rule treats indented lines
        # as code blocks, which suppresses HTML rendering.
        _svg_b64 = base64.b64encode(HERO_SVG.encode()).decode()
        st.markdown(
            f'<div style="text-align:center;margin-bottom:1.25rem">'
            f'<img src="data:image/svg+xml;base64,{_svg_b64}"'
            f' style="width:100%;max-width:400px;display:block;margin:0 auto"/>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<h1 class="hero-title">Write Your Way<br>to Clarity</h1>'
            '<p class="hero-tagline">A daily writing practice, powered by AI.<br>'
            '750 words every morning. Transform your thinking.</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="section-label">Why journal daily?</div>'
            '<div class="benefit-cards">'
            '<div class="benefit-card"><div class="b-icon">🧠</div>'
            '<div class="b-title">Mental Clarity</div>'
            '<div class="b-body">Empty mental clutter onto the page and start your day with focus.</div></div>'
            '<div class="benefit-card"><div class="b-icon">💆</div>'
            '<div class="b-title">Less Stress</div>'
            '<div class="b-body">Writing processes emotions — proven to lower anxiety and cortisol.</div></div>'
            '<div class="benefit-card"><div class="b-icon">🌱</div>'
            '<div class="b-title">Self-Awareness</div>'
            '<div class="b-body">Track patterns, breakthroughs, and how your thinking evolves.</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="section-label">What\'s inside</div>'
            '<div class="feature-items">'
            '<div class="feature-item">📝 <strong>Daily 750-word goal</strong> — the proven sweet spot for morning pages</div>'
            '<div class="feature-item">🤖 <strong>AI-powered insights</strong> — mood trends, themes, and reflections from your writing</div>'
            '<div class="feature-item">💬 <strong>Chat with your journal</strong> — ask questions about what you\'ve written</div>'
            '<div class="feature-item">📅 <strong>Full history &amp; search</strong> — browse and revisit every entry you\'ve made</div>'
            '<div class="feature-item">📥 <strong>Import existing journals</strong> — bring your old writing along</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Right: auth form ─────────────────────────────────────────────────────
    with col_right:
        st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)
        st.markdown("### Get started")

        tab_login, tab_register = st.tabs(["Log In", "Create Account"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log In", use_container_width=True)
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
                reg_submitted = st.form_submit_button("Create Account", use_container_width=True)
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
