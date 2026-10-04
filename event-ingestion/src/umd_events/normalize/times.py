"""Timezone handling. Every timestamp leaving a collector is timezone-aware America/New_York."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from dateutil import parser as dateparser

from ..config import TIMEZONE

MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for m in names
}


def now_eastern() -> datetime:
    return datetime.now(TIMEZONE)


def ensure_eastern(value: datetime) -> datetime:
    """Attach America/New_York to naive datetimes; convert aware ones to it."""
    if value.tzinfo is None:
        return value.replace(tzinfo=TIMEZONE)
    return value.astimezone(TIMEZONE)


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-ish timestamp. Naive values are interpreted as Eastern time."""
    if not value:
        return None
    try:
        return ensure_eastern(dateparser.isoparse(value) if "T" in value else dateparser.parse(value))
    except (ValueError, OverflowError):
        return None


def parse_floating(value: str | None) -> datetime | None:
    """Parse a timestamp whose UTC offset is wrong and whose wall-clock time is local.

    The UMD calendar GraphQL API (Solspace Calendar) returns local times with a bogus ``+00:00`` suffix:
    an event at 3pm EDT comes back as ``15:00:00+00:00``. Drop the offset and treat the time as Eastern.
    """
    if not value:
        return None
    try:
        raw = dateparser.isoparse(value) if "T" in value else dateparser.parse(value)
    except (ValueError, OverflowError):
        return None
    return raw.replace(tzinfo=TIMEZONE)


def combine(day: date, at: time | None) -> datetime:
    return datetime.combine(day, at or time(0, 0), tzinfo=TIMEZONE)


def infer_year(month: int, day: int, reference: date | None = None) -> date:
    """Pick the year that puts month/day closest to the reference date (sites often omit the year)."""
    reference = reference or now_eastern().date()
    candidates = []
    for year in (reference.year - 1, reference.year, reference.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    return min(candidates, key=lambda d: abs((d - reference).days))


_TIME_RE = re.compile(
    r"(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>a\.?\s?m\.?|p\.?\s?m\.?)?",
    re.IGNORECASE,
)


def parse_time_of_day(text: str, default_meridiem: str | None = None) -> time | None:
    """Parse '8:00 PM', '8pm', '7 p.m.', 'noon'. Returns None if there is no time in the text."""
    text = text.strip().lower()
    if text.startswith("noon"):
        return time(12, 0)
    if text.startswith("midnight"):
        return time(0, 0)
    match = _TIME_RE.match(text)
    if not match:
        return None
    hour = int(match.group("h"))
    minute = int(match.group("m") or 0)
    meridiem = (match.group("ampm") or default_meridiem or "").replace(".", "").replace(" ", "")
    if hour > 23 or minute > 59:
        return None
    if meridiem.startswith("p") and hour < 12:
        hour += 12
    elif meridiem.startswith("a") and hour == 12:
        hour = 0
    return time(hour, minute)


_RANGE_RE = re.compile(
    r"(?P<start>(?:\d{1,2}(?::\d{2})?\s*(?:a\.?\s?m\.?|p\.?\s?m\.?)?)|noon)"
    r"\s*(?:to|-|–|—|until)\s*"
    r"(?P<end>(?:\d{1,2}(?::\d{2})?\s*(?:a\.?\s?m\.?|p\.?\s?m\.?)?)|noon|midnight)",
    re.IGNORECASE,
)


def parse_time_range(text: str) -> tuple[time | None, time | None]:
    """Parse '7 to 9 p.m.' / '10:30am - 12pm'. A missing meridiem on the start borrows the end's."""
    match = _RANGE_RE.search(text)
    if match:
        end_text = match.group("end")
        end_meridiem = re.search(r"([ap])\.?\s?m", end_text, re.IGNORECASE)
        end = parse_time_of_day(end_text)
        start = parse_time_of_day(match.group("start"), end_meridiem.group(1) + "m" if end_meridiem else None)
        if start and end and start > end and not re.search(r"[ap]\.?\s?m", match.group("start"), re.I):
            # "11 to 1 p.m." -> 11am to 1pm
            start = parse_time_of_day(match.group("start"), "am")
        return start, end
    single = re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?\s?m\.?|p\.?\s?m\.?)|\bnoon\b", text, re.IGNORECASE)
    return (parse_time_of_day(single.group(0)) if single else None), None


_DATE_RE = re.compile(
    r"(?:(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*\.?,?\s+)?"
    r"(?P<month>jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*\.?\s+"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,?\s+(?P<year>20\d{2}))?",
    re.IGNORECASE,
)


def find_date(text: str, reference: date | None = None) -> date | None:
    """Find the first 'Monday, September 28' / 'October 15th, 2026' style date in free text."""
    match = _DATE_RE.search(text)
    if not match:
        return None
    key = match.group("month").lower()
    month = MONTHS.get(key) or MONTHS[key[:3]]
    day = int(match.group("day"))
    if match.group("year"):
        try:
            return date(int(match.group("year")), month, day)
        except ValueError:
            return None
    try:
        return infer_year(month, day, reference)
    except ValueError:
        return None


def parse_month_day(text: str, reference: date | None = None) -> date | None:
    """Parse '9/28' or '10/7/2026'."""
    match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if not match:
        return None
    month, day = int(match.group(1)), int(match.group(2))
    if match.group(3):
        year = int(match.group(3))
        year += 2000 if year < 100 else 0
        try:
            return date(year, month, day)
        except ValueError:
            return None
    try:
        return infer_year(month, day, reference)
    except ValueError:
        return None


def fix_recurring_end(start: datetime, end: datetime | None, max_hours: int = 24) -> datetime | None:
    """Some feeds report an occurrence's end as the end of the whole series. Clamp it to the start day."""
    if end is None or end - start <= timedelta(hours=max_hours):
        return end
    clamped = start.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    return clamped if clamped > start else None
