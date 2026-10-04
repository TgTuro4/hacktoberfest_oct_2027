"""Title cleanup for display, and aggressive normalization for duplicate matching."""

from __future__ import annotations

import re
import unicodedata

# Organizer prefixes that differ between sources listing the same event.
_PREFIXES = re.compile(
    r"^(?:"
    r"see\s+presents|student entertainment events\s+presents|clarice presents|"
    r"terps after dark|tad|the clarice|umd|maryland athletics|"
    r"stamp programs presents|[a-z .&'-]{2,40}\s+presents"
    r")\s*[:\-–—|]\s*",
    re.IGNORECASE,
)
_RANKING = re.compile(r"#\s?\d+\s+")
_BRACKETS = re.compile(r"\[[^\]]*\]|\((?:rescheduled|updated|new date|cancelled|canceled)[^)]*\)", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def clean_title(title: str) -> str:
    """Light cleanup for display: whitespace, stray punctuation, SHOUTING."""
    title = " ".join(title.replace("​", "").split()).strip(" -–—|:")
    letters = [c for c in title if c.isalpha()]
    if len(letters) > 8 and sum(c.isupper() for c in letters) / len(letters) > 0.85:
        title = title.title()
    return title


def strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def normalize_title(title: str) -> str:
    """'SEE Presents: Spider-Man: Across the Spider-Verse' -> 'spider man across the spider verse'."""
    value = strip_accents(title).lower().strip()
    value = _BRACKETS.sub(" ", value)
    for _ in range(2):  # "Terps After Dark: SEE Presents: ..."
        value = _PREFIXES.sub("", value).strip()
    value = _RANKING.sub("", value)
    value = value.replace("&", " and ").replace("theatre", "theater").replace("'", "").replace("’", "")
    value = _NON_ALNUM.sub(" ", value)
    return " ".join(value.split())
