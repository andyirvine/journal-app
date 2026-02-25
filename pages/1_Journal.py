from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
from datetime import date, datetime
from sqlalchemy.exc import IntegrityError

from core.auth import require_auth
from core.database import JournalEntry, get_db
from core.analysis import compute_sentiment
from core.styles import inject_styles

_db = next(get_db())
require_auth(_db)
_db.close()

inject_styles()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TODAY = date.today()
TARGET_WORDS = 750

# ---------------------------------------------------------------------------
# Load today's entry from DB once (first load only)
# ---------------------------------------------------------------------------
if "journal_content" not in st.session_state:
    db = next(get_db())
    existing = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == st.session_state["user_id"],
            JournalEntry.date == TODAY,
        )
        .first()
    )
    st.session_state["journal_content"] = existing.content if existing else ""
    st.session_state["current_word_count"] = len(st.session_state["journal_content"].split())
    st.session_state["last_saved_time"] = existing.updated_at if existing else None
    db.close()

# Initialize balloon gate
balloon_key = f"balloon_shown_{TODAY}"
if balloon_key not in st.session_state:
    st.session_state[balloon_key] = False

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("Morning Pages")
st.markdown(f"**{TODAY.strftime('%A, %B %d, %Y')}**")

# ---------------------------------------------------------------------------
# Word count callback
# ---------------------------------------------------------------------------
def on_text_change():
    content = st.session_state.get("journal_text_area", "")
    words = content.split()
    st.session_state["current_word_count"] = len(words)
    st.session_state["journal_content"] = content


# ---------------------------------------------------------------------------
# Live word counter — JS reads the textarea directly on every keystroke
# ---------------------------------------------------------------------------
_initial_count = st.session_state["current_word_count"]

components.html(f"""
<style>
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  .row {{ display: flex; gap: 32px; align-items: baseline; margin-bottom: 10px; }}
  .metric {{ text-align: center; min-width: 90px; }}
  .metric-value {{ font-size: 1.9rem; font-weight: 700; color: #2c2825; }}
  .metric-label {{ font-size: 0.72rem; color: #7a7068; margin-top: 2px; text-transform: uppercase; letter-spacing: .05em; }}
  .progress-wrap {{ height: 8px; background: #dedad3; border-radius: 4px; overflow: hidden; }}
  .progress-fill {{ height: 100%; background: #6e8b76; border-radius: 4px; transition: width 0.1s ease; }}
  .progress-fill.done {{ background: #4a7c59; }}
  .celebration {{ margin-top: 8px; font-size: 0.9rem; color: #4a7c59; display: none; }}
</style>
<div class="row">
  <div class="metric">
    <div class="metric-value" id="wc">{_initial_count}</div>
    <div class="metric-label">Words written</div>
  </div>
  <div class="metric">
    <div class="metric-value" id="rem">{max(0, 750 - _initial_count)}</div>
    <div class="metric-label">Words to go</div>
  </div>
  <div class="metric">
    <div class="metric-value" id="pct">{min(100, round(_initial_count / 750 * 100))}%</div>
    <div class="metric-label">Progress</div>
  </div>
</div>
<div class="progress-wrap">
  <div class="progress-fill{'  done' if _initial_count >= 750 else ''}" id="fill"
       style="width:{min(100, round(_initial_count / 750 * 100))}%"></div>
</div>
<div class="celebration" id="cel">🎉 You've hit 750 words — keep going!</div>
<script>
(function() {{
  var TARGET = 750;
  function countWords(t) {{ return t.trim() ? t.trim().split(/\\s+/).length : 0; }}
  function update(n) {{
    var rem = Math.max(0, TARGET - n);
    var pct = Math.min(100, Math.round(n / TARGET * 100));
    document.getElementById('wc').textContent  = n;
    document.getElementById('rem').textContent = rem;
    document.getElementById('pct').textContent = pct + '%';
    var fill = document.getElementById('fill');
    fill.style.width = pct + '%';
    fill.className = 'progress-fill' + (n >= TARGET ? ' done' : '');
    document.getElementById('cel').style.display = n >= TARGET ? 'block' : 'none';
  }}
  function attach() {{
    var ta = window.parent.document.querySelector('[data-testid="stTextArea"] textarea');
    if (!ta) {{ setTimeout(attach, 200); return; }}
    update(countWords(ta.value));
    ta.addEventListener('input', function() {{ update(countWords(this.value)); }});
  }}
  attach();
}})();
</script>
""", height=100)

# Python-side balloon gate still fires on save/rerun
word_count = st.session_state["current_word_count"]
if word_count >= TARGET_WORDS and not st.session_state[balloon_key]:
    st.balloons()
    st.session_state[balloon_key] = True

# ---------------------------------------------------------------------------
# Text area — never set value= to a session_state key to avoid circular dep
# ---------------------------------------------------------------------------
st.text_area(
    label="Write freely — no one is judging you.",
    value=st.session_state["journal_content"],
    height=500,
    key="journal_text_area",
    on_change=on_text_change,
    placeholder="Start writing... your thoughts, dreams, worries, gratitude. Anything goes.",
)

# ---------------------------------------------------------------------------
# Save button
# ---------------------------------------------------------------------------
save_col, info_col = st.columns([1, 3])
with save_col:
    save_clicked = st.button("Save", use_container_width=True, type="primary")

if save_clicked:
    content = st.session_state.get("journal_text_area", st.session_state["journal_content"])
    wc = len(content.split()) if content.strip() else 0
    sentiment = compute_sentiment(content) if content.strip() else None

    db = next(get_db())
    try:
        entry = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == st.session_state["user_id"],
                JournalEntry.date == TODAY,
            )
            .first()
        )
        now = datetime.utcnow()
        if entry:
            entry.content = content
            entry.word_count = wc
            entry.sentiment_score = sentiment
            entry.updated_at = now
        else:
            entry = JournalEntry(
                user_id=st.session_state["user_id"],
                date=TODAY,
                content=content,
                word_count=wc,
                sentiment_score=sentiment,
                created_at=now,
                updated_at=now,
            )
            db.add(entry)
        db.commit()
        st.session_state["last_saved_time"] = now
        st.rerun()
    except Exception as exc:
        db.rollback()
        st.error(f"Save failed: {exc}")
    finally:
        db.close()

with info_col:
    last_saved = st.session_state.get("last_saved_time")
    if last_saved:
        # Convert UTC to local display time (best effort)
        try:
            local_time = datetime.fromtimestamp(last_saved.timestamp())
            st.caption(f"Last saved: {local_time.strftime('%I:%M %p')}")
        except Exception:
            st.caption(f"Last saved: {last_saved.strftime('%H:%M UTC')}")
