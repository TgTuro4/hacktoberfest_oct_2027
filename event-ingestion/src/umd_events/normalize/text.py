from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup

_WS = re.compile(r"[ \t ​]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = html.unescape(value).replace("\r", "")
    value = _WS.sub(" ", value)
    value = "\n".join(line.strip() for line in value.split("\n"))
    value = _BLANK_LINES.sub("\n\n", value).strip()
    return value or None


def html_to_text(value: str | None) -> str | None:
    """Convert an HTML fragment to readable plain text, keeping paragraph breaks."""
    if not value:
        return None
    if "<" not in value:
        return clean_text(value)
    soup = BeautifulSoup(value, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "tr"]):
        block.insert_after("\n")
    return clean_text(soup.get_text())


def summarize(text: str | None, limit: int = 220) -> str | None:
    """First sentence(s) of a description, cut at a word boundary."""
    if not text:
        return None
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    sentence_end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if sentence_end > limit * 0.5:
        return cut[: sentence_end + 1]
    return cut[: cut.rfind(" ")].rstrip(",;:-") + "…"
