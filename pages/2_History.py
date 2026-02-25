from __future__ import annotations

import streamlit as st
from datetime import date

from core.auth import require_auth
from core.database import JournalEntry, get_db
from core.styles import inject_styles

_db = next(get_db())
require_auth(_db)
_db.close()

inject_styles()
st.title("Journal History")

# ---------------------------------------------------------------------------
# Fetch all entries for this user
# ---------------------------------------------------------------------------
db = next(get_db())
entries = (
    db.query(JournalEntry)
    .filter(JournalEntry.user_id == st.session_state["user_id"])
    .order_by(JournalEntry.date.asc())
    .all()
)
db.close()

if not entries:
    st.info("No journal entries yet. Start writing in the Journal page!")
    st.stop()

# ---------------------------------------------------------------------------
# Build FullCalendar events
# ---------------------------------------------------------------------------
def sentiment_color(score) -> str:
    if score is None:
        return "#9e9e9e"  # gray
    if score >= 0.05:
        return "#4caf50"  # green
    if score <= -0.05:
        return "#f44336"  # red
    return "#ff9800"  # amber


events = []
entry_map: dict[str, JournalEntry] = {}

for e in entries:
    date_str = e.date.isoformat()
    wc = e.word_count or 0
    title = f"{wc}w" + (" ✓" if wc >= 750 else "")
    events.append({
        "title": title,
        "start": date_str,
        "backgroundColor": sentiment_color(e.sentiment_score),
        "borderColor": sentiment_color(e.sentiment_score),
        "textColor": "#ffffff",
        "extendedProps": {"date": date_str},
    })
    entry_map[date_str] = e

# ---------------------------------------------------------------------------
# Modal dialog
# ---------------------------------------------------------------------------
@st.dialog("Journal Entry", width="large")
def show_entry_modal(entry, date_str):
    st.caption(f"{date_str} · {entry.word_count or 0} words")
    if entry.sentiment_score is not None:
        score = entry.sentiment_score
        label = "Positive" if score >= 0.05 else ("Negative" if score <= -0.05 else "Neutral")
        st.caption(f"Sentiment: {label} ({score:+.2f})")
    st.text_area(
        "",
        value=entry.content,
        height=500,
        disabled=True,
        key=f"modal_entry_{date_str}",
        label_visibility="collapsed",
    )

# ---------------------------------------------------------------------------
# Calendar (full width)
# ---------------------------------------------------------------------------
try:
    from streamlit_calendar import calendar as st_calendar

    calendar_options = {
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,listMonth",
        },
        "initialView": "dayGridMonth",
        "selectable": True,
        "editable": False,
        "height": 650,
    }

    result = st_calendar(events=events, options=calendar_options, key="history_calendar")

    # Capture event click
    if result and result.get("eventClick"):
        clicked_date = result["eventClick"]["event"].get("extendedProps", {}).get("date")
        if clicked_date:
            st.session_state["selected_history_date"] = clicked_date
            st.session_state["open_entry_modal"] = True

    # Open modal if triggered (reset flag first so it doesn't reopen after close)
    if st.session_state.get("open_entry_modal"):
        st.session_state["open_entry_modal"] = False
        selected_date = st.session_state.get("selected_history_date")
        if selected_date and selected_date in entry_map:
            show_entry_modal(entry_map[selected_date], selected_date)

except ImportError:
    st.warning("Install `streamlit-calendar` for the calendar view. Showing list instead.")
    st.divider()
    for e in reversed(entries):
        with st.expander(f"{e.date.isoformat()} — {e.word_count or 0} words"):
            st.text(e.content)

# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------
st.divider()
legend_cols = st.columns(4)
legend_cols[0].markdown("🟢 **Positive** sentiment")
legend_cols[1].markdown("🟠 **Neutral** sentiment")
legend_cols[2].markdown("🔴 **Negative** sentiment")
legend_cols[3].markdown("⚪ **No score** yet")
