from __future__ import annotations

import os
from collections import Counter
from typing import List, Optional, Tuple

import nltk
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# ---------------------------------------------------------------------------
# NLTK resource setup (handles 3.9 rename of punkt_tab)
# ---------------------------------------------------------------------------

def _ensure_nltk_resources() -> None:
    resources = [
        ("tokenizers/punkt_tab", "punkt_tab"),
        ("corpora/stopwords", "stopwords"),
    ]
    for path, name in resources:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(name, quiet=True)


_ensure_nltk_resources()

from nltk.corpus import stopwords  # noqa: E402
from nltk.tokenize import word_tokenize  # noqa: E402

_ANALYZER = SentimentIntensityAnalyzer()
_STOP_WORDS = set(stopwords.words("english"))

# Domain noise words common in journaling
_NOISE_WORDS = {
    "just", "really", "think", "know", "want", "need", "feel", "like",
    "going", "things", "thing", "time", "today", "also", "still", "even",
    "make", "good", "much", "well", "back", "year", "years", "week", "day",
    "life", "little", "right", "something", "never", "always", "everything",
    "nothing", "actually", "definitely", "probably", "maybe", "would",
    "could", "should", "might", "this", "that", "these", "those",
}


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------

def compute_sentiment(text: str) -> float:
    scores = _ANALYZER.polarity_scores(text)
    return scores["compound"]


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

def extract_keywords(text: str, top_n: int = 20) -> List[Tuple[str, int]]:
    tokens = word_tokenize(text.lower())
    words = [
        w for w in tokens
        if w.isalpha()
        and len(w) > 3
        and w not in _STOP_WORDS
        and w not in _NOISE_WORDS
    ]
    counter = Counter(words)
    return counter.most_common(top_n)


# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------

def _get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def get_narrative_observation(content: str) -> str:
    client = _get_client()
    if not client:
        return "Set ANTHROPIC_API_KEY in your .env file to enable AI observations."

    capped = content[:8000]
    prompt = (
        "You are a warm, non-judgmental journaling companion. "
        "The user has shared their morning pages with you. "
        "Write 3-4 sentences reflecting back what you notice in their writing — "
        "themes, feelings, energy, or tensions — without giving advice, "
        "without quoting them directly, and in second person. "
        "Be gentle, curious, and affirming.\n\n"
        f"Journal entry:\n{capped}"
    )

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as exc:
        return f"Could not generate observation: {exc}"


def get_contextual_insight(current_entry: str, history_entries: list) -> str:
    client = _get_client()
    if not client:
        return "Set ANTHROPIC_API_KEY in your .env file to enable AI insights."

    def summarize(entry_content: str) -> str:
        if len(entry_content) <= 700:
            return entry_content
        return entry_content[:500] + " ... " + entry_content[-200:]

    history_text = ""
    for entry in history_entries:  # expected: list of dicts with 'date' and 'content'
        entry_date = entry.get("date", "unknown date")
        snippet = summarize(entry.get("content", ""))
        history_text += f"\n--- {entry_date} ---\n{snippet}\n"

    current_capped = current_entry[:8000]
    prompt = (
        "You are a warm, non-judgmental journaling companion. "
        "Below is the user's recent journaling history (oldest to newest), "
        "followed by today's entry. "
        "Write 4-5 sentences noticing patterns, shifts in mood or focus, "
        "or threads that run across their entries — without giving advice, "
        "without quoting them directly, and in second person. "
        "Be curious and gentle.\n\n"
        f"Recent history:{history_text}\n"
        f"--- Today ---\n{current_capped}"
    )

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as exc:
        return f"Could not generate insight: {exc}"
