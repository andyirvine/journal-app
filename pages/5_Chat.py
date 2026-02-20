from __future__ import annotations

import os
from datetime import datetime

import streamlit as st

st.set_page_config(page_title="Chat", page_icon="💬", layout="wide")

from core.auth import require_auth
from core.database import ChatLog, JournalEntry, get_db
from core.analysis import answer_journal_question

_db = next(get_db())
require_auth(_db)
_db.close()

st.title("💬 Ask Your Journal")
st.caption("Ask anything about your writing — themes, patterns, emotions, specific memories.")

# ---------------------------------------------------------------------------
# Check API key
# ---------------------------------------------------------------------------
if not os.getenv("ANTHROPIC_API_KEY"):
    st.info("Set `ANTHROPIC_API_KEY` in your `.env` file to use journal chat.")
    st.stop()

# ---------------------------------------------------------------------------
# Fetch entries
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
    st.info("No journal entries yet — start writing to use this feature.")
    st.stop()

entry_data = [
    {"date": e.date.isoformat(), "content": e.content, "word_count": e.word_count or 0}
    for e in entries
]

st.caption(f"Drawing on {len(entries)} entries across your journal.")

# ---------------------------------------------------------------------------
# Chat state
# ---------------------------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

if st.session_state["chat_history"]:
    if st.button("Clear conversation", type="secondary"):
        st.session_state["chat_history"] = []
        st.rerun()

# ---------------------------------------------------------------------------
# Display current conversation
# ---------------------------------------------------------------------------
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
if question := st.chat_input("Ask a question about your journal…"):
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            history = st.session_state["chat_history"][-10:]
            answer = answer_journal_question(question, entry_data, history)
        st.markdown(answer)

    # Save to DB
    db = next(get_db())
    db.add(ChatLog(
        user_id=st.session_state["user_id"],
        question=question,
        answer=answer,
    ))
    db.commit()
    db.close()

    st.session_state["chat_history"].append({"role": "user", "content": question})
    st.session_state["chat_history"].append({"role": "assistant", "content": answer})

# ---------------------------------------------------------------------------
# Past conversations
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Past Conversations")

db = next(get_db())
past_logs = (
    db.query(ChatLog)
    .filter(ChatLog.user_id == st.session_state["user_id"])
    .order_by(ChatLog.created_at.desc())
    .limit(50)
    .all()
)
db.close()

if not past_logs:
    st.caption("No saved conversations yet.")
else:
    for log in past_logs:
        local_time = datetime.fromtimestamp(log.created_at.timestamp())
        label = f"{local_time.strftime('%B %d, %Y · %I:%M %p')} — {log.question[:60]}{'…' if len(log.question) > 60 else ''}"
        with st.expander(label):
            st.markdown(f"**You:** {log.question}")
            st.markdown(f"**Claude:** {log.answer}")
