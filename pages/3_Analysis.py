from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

from core.auth import require_auth
from core.database import AIInsight, JournalEntry, get_db
from core.analysis import extract_keywords, get_narrative_observation, get_contextual_insight
from core.styles import inject_styles

_db = next(get_db())
require_auth(_db)
_db.close()

inject_styles()
st.title("Analysis & Insights")

# ---------------------------------------------------------------------------
# Fetch all entries
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
    st.info("No entries yet — start journaling to see analysis here.")
    st.stop()

# ---------------------------------------------------------------------------
# Stats row
# ---------------------------------------------------------------------------
total_words = sum(e.word_count or 0 for e in entries)
days_journaled = len(entries)
days_750_plus = sum(1 for e in entries if (e.word_count or 0) >= 750)
pct_750 = int(days_750_plus / days_journaled * 100) if days_journaled else 0

# Current streak (consecutive days up to today)
entry_dates = {e.date for e in entries}
streak = 0
check = date.today()
while check in entry_dates:
    streak += 1
    check -= timedelta(days=1)

s1, s2, s3, s4 = st.columns(4)
s1.metric("Total words written", f"{total_words:,}")
s2.metric("Days journaled", days_journaled)
s3.metric("750+ word days", f"{days_750_plus} ({pct_750}%)")
s4.metric("Current streak", f"{streak} day{'s' if streak != 1 else ''}")

st.divider()

# ---------------------------------------------------------------------------
# Date range filter
# ---------------------------------------------------------------------------
range_options = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All time": None}
selected_range = st.selectbox("Date range", list(range_options.keys()), index=1)
days_back = range_options[selected_range]

if days_back:
    cutoff = date.today() - timedelta(days=days_back)
    filtered = [e for e in entries if e.date >= cutoff]
else:
    filtered = entries

if not filtered:
    st.warning("No entries in the selected date range.")
    st.stop()

# ---------------------------------------------------------------------------
# Sentiment chart
# ---------------------------------------------------------------------------
st.subheader("Sentiment Over Time")

dates_with_scores = [(e.date, e.sentiment_score) for e in filtered if e.sentiment_score is not None]

if dates_with_scores:
    chart_dates = [d for d, _ in dates_with_scores]
    chart_scores = [s for _, s in dates_with_scores]

    # 7-day rolling average
    rolling_avg = []
    for i, (d, _) in enumerate(dates_with_scores):
        window = [s for dd, s in dates_with_scores if (d - dd).days <= 7 and (d - dd).days >= 0]
        rolling_avg.append(sum(window) / len(window))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=chart_dates, y=chart_scores,
        mode="markers",
        name="Daily",
        marker=dict(
            color=chart_scores,
            colorscale=[[0, "#f44336"], [0.5, "#ff9800"], [1, "#4caf50"]],
            cmin=-1, cmax=1,
            size=8,
        ),
    ))
    fig.add_trace(go.Scatter(
        x=chart_dates, y=rolling_avg,
        mode="lines",
        name="7-day avg",
        line=dict(color="#6e8b76", width=2),
        fill="tozeroy",
        fillcolor="rgba(110,139,118,0.1)",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        yaxis=dict(title="Sentiment score", range=[-1.1, 1.1]),
        xaxis=dict(title="Date"),
        height=350,
        legend=dict(orientation="h"),
        margin=dict(t=20),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No sentiment scores yet — save an entry to compute sentiment.")

st.divider()

# ---------------------------------------------------------------------------
# Keyword frequency chart
# ---------------------------------------------------------------------------
st.subheader("Most Common Words")

all_text = " ".join(e.content for e in filtered)
keywords = extract_keywords(all_text, top_n=20)

if keywords:
    kw_words = [w for w, _ in keywords]
    kw_counts = [c for _, c in keywords]

    fig2 = go.Figure(go.Bar(
        x=kw_counts[::-1],
        y=kw_words[::-1],
        orientation="h",
        marker_color="#8ea89a",
    ))
    fig2.update_layout(
        height=450,
        xaxis=dict(title="Frequency"),
        yaxis=dict(title=""),
        margin=dict(t=20),
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Not enough text to extract keywords yet.")

st.divider()

# ---------------------------------------------------------------------------
# Claude AI insights
# ---------------------------------------------------------------------------
st.subheader("AI Observations")

has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))
today = date.today()

today_entries = [e for e in entries if e.date == today]
today_entry = today_entries[0] if today_entries else None
today_word_count = today_entry.word_count if today_entry else 0

if not has_api_key:
    st.info("Set `ANTHROPIC_API_KEY` in your `.env` file to enable AI-powered insights.")
elif not today_entry or today_word_count < 50:
    st.info("Write at least 50 words in today's entry to unlock AI observations.")
else:
    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        if st.button("Narrative Observation", use_container_width=True):
            with st.spinner("Generating observation..."):
                obs = get_narrative_observation(today_entry.content)
            st.session_state["narrative_observation"] = obs
            # Save to DB
            db = next(get_db())
            db.add(AIInsight(
                user_id=st.session_state["user_id"],
                entry_date=today,
                insight_type="narrative",
                content=obs,
            ))
            db.commit()
            db.close()

    with btn_col2:
        if st.button("Contextual Insight", use_container_width=True):
            history = [
                {"date": e.date.isoformat(), "content": e.content}
                for e in entries
                if e.date != today
            ][-7:]
            with st.spinner("Generating contextual insight..."):
                insight = get_contextual_insight(today_entry.content, history)
            st.session_state["contextual_insight"] = insight
            # Save to DB
            db = next(get_db())
            db.add(AIInsight(
                user_id=st.session_state["user_id"],
                entry_date=today,
                insight_type="contextual",
                content=insight,
            ))
            db.commit()
            db.close()

    # Show cached results from this session
    if "narrative_observation" in st.session_state:
        st.markdown("**Narrative Observation**")
        st.markdown(st.session_state["narrative_observation"])

    if "contextual_insight" in st.session_state:
        st.markdown("**Contextual Insight**")
        st.markdown(st.session_state["contextual_insight"])

# ---------------------------------------------------------------------------
# Past AI insights
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Past Insights")

db = next(get_db())
past_insights = (
    db.query(AIInsight)
    .filter(AIInsight.user_id == st.session_state["user_id"])
    .order_by(AIInsight.created_at.desc())
    .limit(50)
    .all()
)
db.close()

if not past_insights:
    st.caption("No saved insights yet — generate one above.")
else:
    for insight in past_insights:
        label = "Narrative Observation" if insight.insight_type == "narrative" else "Contextual Insight"
        local_time = datetime.fromtimestamp(insight.created_at.timestamp())
        header = f"{label} — {insight.entry_date.strftime('%B %d, %Y')} · {local_time.strftime('%I:%M %p')}"
        with st.expander(header):
            st.markdown(insight.content)
