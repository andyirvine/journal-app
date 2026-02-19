from __future__ import annotations

import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Import", page_icon="📥", layout="wide")

from core.auth import require_auth
from core.database import JournalEntry, get_db
from core.analysis import compute_sentiment
from core.importer import parse_upload

_db = next(get_db())
require_auth(_db)
_db.close()

st.title("📥 Import Entries")
st.markdown(
    "Import journal entries from plain text (`.txt`), Markdown (`.md`), "
    "or a 750words.com export (`.zip` or single combined file)."
)

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
uploaded = st.file_uploader(
    "Choose a file to import",
    type=["txt", "md", "zip"],
    accept_multiple_files=False,
)

if not uploaded:
    st.stop()

file_bytes = uploaded.read()
parsed_entries, warnings = parse_upload(uploaded.name, file_bytes)

# Show warnings
for w in warnings:
    st.warning(w)

if not parsed_entries:
    st.error("No entries could be parsed from this file.")
    st.stop()

st.success(f"Found **{len(parsed_entries)}** entries.")

# Preview first 5
st.subheader("Preview (first 5 entries)")
for entry in parsed_entries[:5]:
    with st.expander(f"{entry['date'].isoformat()} — {len(entry['content'].split())} words"):
        st.text(entry["content"][:500] + ("..." if len(entry["content"]) > 500 else ""))

# ---------------------------------------------------------------------------
# Conflict strategy
# ---------------------------------------------------------------------------
conflict = st.radio(
    "If an entry already exists for that date:",
    ["Skip existing", "Overwrite existing"],
    horizontal=True,
)

# ---------------------------------------------------------------------------
# Import button
# ---------------------------------------------------------------------------
if st.button("⬆️ Import Entries", type="primary"):
    db = next(get_db())
    user_id = st.session_state["user_id"]

    imported = 0
    skipped = 0
    errors = 0

    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(parsed_entries)

    batch_size = 10
    for batch_start in range(0, total, batch_size):
        batch = parsed_entries[batch_start : batch_start + batch_size]
        for i, item in enumerate(batch):
            abs_idx = batch_start + i
            status_text.text(f"Processing {abs_idx + 1}/{total}...")
            progress_bar.progress((abs_idx + 1) / total)

            try:
                content = item["content"]
                entry_date = item["date"]
                wc = len(content.split())
                sentiment = compute_sentiment(content) if content.strip() else None
                now = datetime.utcnow()

                existing = (
                    db.query(JournalEntry)
                    .filter(
                        JournalEntry.user_id == user_id,
                        JournalEntry.date == entry_date,
                    )
                    .first()
                )

                if existing:
                    if conflict == "Skip existing":
                        skipped += 1
                        continue
                    else:
                        existing.content = content
                        existing.word_count = wc
                        existing.sentiment_score = sentiment
                        existing.updated_at = now
                        imported += 1
                else:
                    new_entry = JournalEntry(
                        user_id=user_id,
                        date=entry_date,
                        content=content,
                        word_count=wc,
                        sentiment_score=sentiment,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(new_entry)
                    imported += 1

            except Exception as exc:
                errors += 1
                st.error(f"Error on {item.get('date', 'unknown date')}: {exc}")

        # Commit every batch
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            st.error(f"Batch commit failed: {exc}")
            errors += len(batch)
            imported -= len(batch)

    db.close()
    status_text.empty()
    progress_bar.empty()

    st.divider()
    result_cols = st.columns(3)
    result_cols[0].metric("Imported", imported)
    result_cols[1].metric("Skipped", skipped)
    result_cols[2].metric("Errors", errors)

    if errors == 0:
        st.success("Import complete!")
    else:
        st.warning(f"Import finished with {errors} error(s). Check the messages above.")
