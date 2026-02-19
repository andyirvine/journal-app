from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

_ISO_DATE_RE = re.compile(r"(\d{4})[-_](\d{2})[-_](\d{2})")
_NATURAL_DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date_from_string(s: str) -> Optional[date]:
    m = _ISO_DATE_RE.search(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = _NATURAL_DATE_RE.search(s)
    if m:
        month = _MONTH_MAP[m.group(1).lower()]
        day = int(m.group(2))
        year = int(m.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"={3,}\s*\S.*?\s*={3,}", re.MULTILINE)


def detect_format(filename: str, content: str) -> str:
    name_lower = filename.lower()
    if name_lower.endswith(".zip"):
        return "zip_750words"
    if _HEADER_RE.search(content):
        return "single_750words"
    if _parse_date_from_string(filename) is not None:
        return "dated_file"
    return "undated_file"


# ---------------------------------------------------------------------------
# Parsed entry type
# ---------------------------------------------------------------------------

ParsedEntry = dict  # keys: date (date), content (str)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_zip_750words(file_bytes: bytes) -> Tuple[List[ParsedEntry], List[str]]:
    entries: List[ParsedEntry] = []
    warnings: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith("/") or name.startswith("__MACOSX"):
                    continue
                entry_date = _parse_date_from_string(name)
                if entry_date is None:
                    warnings.append(f"Could not parse date from filename: {name} — skipped.")
                    continue
                raw = zf.read(name)
                content = _decode(raw)
                entries.append({"date": entry_date, "content": content.strip()})
    except zipfile.BadZipFile as exc:
        warnings.append(f"Invalid zip file: {exc}")
    return entries, warnings


def parse_single_750words(text: str) -> Tuple[List[ParsedEntry], List[str]]:
    """Parse a single file containing multiple entries separated by === date === headers."""
    entries: List[ParsedEntry] = []
    warnings: List[str] = []
    # Split on header lines like "=== January 5, 2024 ===" or "=== 2024-01-05 ==="
    parts = _HEADER_RE.split(text)
    headers = _HEADER_RE.findall(text)

    if not headers:
        # Single block with no headers
        return [], ["No date headers found — use 'dated file' import instead."]

    # parts[0] is content before first header (usually empty)
    for header, content in zip(headers, parts[1:]):
        entry_date = _parse_date_from_string(header)
        if entry_date is None:
            warnings.append(f"Could not parse date from header '{header.strip()}' — skipped.")
            continue
        entries.append({"date": entry_date, "content": content.strip()})

    return entries, warnings


def parse_dated_file(filename: str, file_bytes: bytes) -> Tuple[List[ParsedEntry], List[str]]:
    entry_date = _parse_date_from_string(filename)
    warnings: List[str] = []
    if entry_date is None:
        return [], [f"Could not parse date from filename: {filename}"]
    content = _decode(file_bytes)
    return [{"date": entry_date, "content": content.strip()}], warnings


def parse_undated_file(file_bytes: bytes) -> Tuple[List[ParsedEntry], List[str]]:
    content = _decode(file_bytes)
    today = date.today()
    warnings = [
        f"No date found in filename — imported as today ({today.isoformat()}). "
        "Edit the entry date if needed."
    ]
    return [{"date": today, "content": content.strip()}], warnings


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_upload(filename: str, file_bytes: bytes) -> Tuple[List[ParsedEntry], List[str]]:
    content_str = _decode(file_bytes) if not filename.lower().endswith(".zip") else ""
    fmt = detect_format(filename, content_str)

    if fmt == "zip_750words":
        return parse_zip_750words(file_bytes)
    elif fmt == "single_750words":
        return parse_single_750words(content_str)
    elif fmt == "dated_file":
        return parse_dated_file(filename, file_bytes)
    else:
        return parse_undated_file(file_bytes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
