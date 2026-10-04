"""Shared iCalendar collector for CivicPlus city websites (College Park, Hyattsville)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, ClassVar

from icalendar import Calendar

from ..models import Event, RawEvent
from ..normalize.text import clean_text, html_to_text, summarize
from ..normalize.times import combine, ensure_eastern
from .base import BaseCollector

ICS_PATH = "/common/modules/iCalendar/iCalendar.aspx?catID={cat}&feed=calendar"
_URL_IN_TEXT = re.compile(r"https?://\S+")
# Civic business rather than things to attend for fun.
DEFAULT_EXCLUDE = re.compile(
    r"\b(council|commission|committee|board of|work session|hearing|public meeting|election|early voting|"
    r"mail-in|ballot|budget|closed for|offices? closed|hr use|rehearsal|girl scout|ballet school)\b",
    re.I,
)


def ics_to_records(content: bytes, category: str) -> list[dict[str, Any]]:
    """Flatten VEVENTs into JSON-serializable dicts (the raw payload stored in RAW_EVENTS)."""
    records = []
    for component in Calendar.from_ical(content).walk("VEVENT"):
        def value(key: str) -> Any:
            prop = component.get(key)
            if prop is None:
                return None
            if hasattr(prop, "dt"):
                dt = prop.dt
                return dt.isoformat() if isinstance(dt, (datetime, date)) else str(dt)
            return str(prop)

        records.append({
            "uid": value("UID"),
            "summary": value("SUMMARY"),
            "description": value("DESCRIPTION"),
            "location": value("LOCATION"),
            "dtstart": value("DTSTART"),
            "dtend": value("DTEND"),
            "last_modified": value("LAST-MODIFIED"),
            "category": category,
        })
    return records


def parse_ics_datetime(value: str | None) -> tuple[datetime | None, bool]:
    if not value:
        return None, False
    if len(value) == 10:  # all-day DATE value
        return combine(date.fromisoformat(value), None), True
    return ensure_eastern(datetime.fromisoformat(value)), False


def split_location(location: str | None) -> tuple[str | None, str | None]:
    """'City Facilities > City Hall Plaza - 7401 Baltimore Avenue  College Park MD 20740' -> (venue, address)."""
    text = html_to_text(location)
    if not text:
        return None, None
    text = " ".join(text.split())
    if text.startswith("-"):  # no facility name: "- Art Works Now 4800 Rhode Island Ave Hyattsville MD 20781"
        name, address = "", text.lstrip("- ")
    else:
        name, _, address = text.partition(" - ")
    name = name.split(">")[-1].strip()
    address = address.strip()
    if not name and address:
        split = re.match(r"^(\D+?)\s+(\d+\s.+)$", address)  # "Art Works Now" + "4800 Rhode Island Ave ..."
        if split:
            name, address = split.group(1), split.group(2)
    return name or None, address or None


class CivicPlusCollector(BaseCollector):
    base_url: ClassVar[str]
    # catID -> human-readable category name
    categories: ClassVar[dict[int, str]]
    exclude: ClassVar[re.Pattern] = DEFAULT_EXCLUDE
    organizer: ClassVar[str]
    tier = 1

    def fetch(self) -> list[RawEvent]:
        by_uid: dict[str, dict[str, Any]] = {}
        for cat_id, name in self.categories.items():
            content = self.http.get(self.base_url + ICS_PATH.format(cat=cat_id)).content
            for record in ics_to_records(content, name):
                if record["uid"]:
                    existing = by_uid.setdefault(record["uid"], {**record, "categories": []})
                    existing["categories"].append(name)
        return [self.raw(uid, rec, self.event_url(uid)) for uid, rec in by_uid.items()]

    def event_url(self, uid: str) -> str:
        return f"{self.base_url}/Calendar.aspx?EID={uid}"

    def parse(self, raw: RawEvent) -> list[Event]:
        d = raw.raw_data
        title = clean_text(d.get("summary"))
        if not title or self.exclude.search(title):
            return []
        start, all_day = parse_ics_datetime(d.get("dtstart"))
        end, _ = parse_ics_datetime(d.get("dtend"))
        venue, address = split_location(d.get("location"))
        description = clean_text(_URL_IN_TEXT.sub("", d.get("description") or ""))
        return [
            self.event(
                source_event_id=raw.source_event_id,
                source_url=self.event_url(raw.source_event_id),
                title=title,
                description=description,
                summary=summarize(description),
                start_time=start,
                end_time=end if end and end > start else None,
                all_day=all_day,
                venue_name=venue,
                address=address,
                organizer_name=self.organizer,
                is_umd=False,
                source_categories=list(d.get("categories") or [d.get("category")]),
            )
        ]
