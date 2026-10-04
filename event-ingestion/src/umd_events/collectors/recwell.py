"""UMD Recreation & Wellness: intramural sports registration windows and league start dates.

RecWell has no event feed. The intramural calendar page publishes a table of
Sport | Registration Begins | Registration Closes | Play Begins, which becomes registration_open,
registration_deadline and activity events.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from ..models import Event, RawEvent
from ..normalize.text import clean_text
from ..normalize.times import combine, parse_month_day
from ..normalize.titles import normalize_title
from .base import BaseCollector, register

CALENDAR_URL = "https://recwell.umd.edu/programs-activities/intramural-sports/intramural-sports-calendar"
REGISTER_URL = "https://www.imleagues.com/spa/network/4395e0c781af4905a4088a9561509399/home"

COLUMN_KINDS = (
    ("registration_open", re.compile(r"regist.*(begin|open|start)", re.I)),
    ("registration_deadline", re.compile(r"regist.*(clos|end|deadline|due)", re.I)),
    ("activity", re.compile(r"play|tournament|event date|date|begins", re.I)),
)
TITLES = {
    "registration_open": "Intramural {sport}: Registration Opens",
    "registration_deadline": "Intramural {sport}: Registration Deadline",
    "activity": "Intramural {sport}: Play Begins",
}


def extract_rows(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for table in soup.find_all("table"):
        headers = [clean_text(th.get_text(" ", strip=True)) or "" for th in table.select("thead th")]
        if not headers or not re.search(r"sport|activity|event", headers[0], re.I):
            continue
        kinds: dict[int, str] = {}
        for index, header in enumerate(headers[1:], start=1):
            for kind, pattern in COLUMN_KINDS:
                if pattern.search(header) and kind not in kinds.values():
                    kinds[index] = kind
                    break
        for tr in table.select("tbody tr"):
            cells = [clean_text(td.get_text(" ", strip=True)) or "" for td in tr.find_all("td")]
            if len(cells) < 2 or not cells[0]:
                continue
            rows.append({"sport": cells[0], "headers": headers,
                         "dates": {kinds[i]: cells[i] for i in kinds if i < len(cells) and cells[i]}})
    return rows


@register
class RecWellCollector(BaseCollector):
    source_name = "recwell"
    display_name = "UMD RecWell"
    scraper_version = "1"
    tier = 2

    def fetch(self) -> list[RawEvent]:
        rows = extract_rows(self.http.get_text(CALENDAR_URL))
        return [self.raw(normalize_title(r["sport"]).replace(" ", "-"), r, CALENDAR_URL) for r in rows]

    def parse(self, raw: RawEvent) -> list[Event]:
        d = raw.raw_data
        events = []
        for kind, text in d["dates"].items():
            day = parse_month_day(text, reference=self.now.date())
            if day is None:
                continue
            events.append(
                self.event(
                    source_event_id=f"{raw.source_event_id}:{kind}",
                    source_url=CALENDAR_URL,
                    title=TITLES[kind].format(sport=d["sport"]),
                    summary=f"UMD Intramural Sports {d['sport']}: "
                    + {"registration_open": "team registration opens on IMLeagues.",
                       "registration_deadline": "last day to register a team on IMLeagues.",
                       "activity": "league play begins."}[kind],
                    start_time=combine(day, None),
                    all_day=True,
                    venue_name="Online (IMLeagues)" if kind != "activity" else None,
                    organizer_name="UMD Recreation & Wellness",
                    registration_url=REGISTER_URL,
                    is_umd=True,
                    is_online=kind != "activity",
                    event_type=kind,
                    tags=["intramural", "sports"],
                    extra={"sport": d["sport"], "date_text": text},
                )
            )
        return events
