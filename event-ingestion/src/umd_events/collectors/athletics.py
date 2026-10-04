"""Maryland Athletics (umterps.com, a SIDEARM Sports site). Uses the JSON feed behind the composite calendar."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ..models import Event, RawEvent
from ..normalize.times import parse_datetime, parse_time_of_day
from ..normalize.urls import clean_url
from .base import BaseCollector, register

BASE = "https://umterps.com"
FEED_URL = f"{BASE}/services/responsive-calendar.ashx"
_RANK = re.compile(r"^\s*(?:#|No\.\s*)\d+\s+")
# Home venue by sport, for games whose feed entry has no facility.
SPORT_VENUES = (
    ("football", "SECU Stadium"),
    ("basketball", "Xfinity Center"),
    ("volleyball", "Xfinity Center"),
    ("wrestling", "Xfinity Center"),
    ("gymnastics", "Xfinity Center"),
    ("softball", "Robert E. Taylor Softball Stadium"),
    ("baseball", "Bob \"Turtle\" Smith Stadium"),
    ("field hockey", "Field Hockey & Lacrosse Complex"),
    ("lacrosse", "SECU Stadium"),
    ("soccer", "Ludwig Field"),
    ("track", "Ludwig Field"),
)


def default_venue(sport: str) -> str | None:
    sport = sport.lower()
    return next((venue for key, venue in SPORT_VENUES if key in sport), None)


def is_home(event: dict[str, Any]) -> bool:
    return event.get("location_indicator") == "H" or "college park" in (event.get("location") or "").lower()


@register
class AthleticsCollector(BaseCollector):
    source_name = "umd_athletics"
    display_name = "Maryland Athletics"
    scraper_version = "1"

    def months(self) -> list[date]:
        first = self.now.date().replace(day=1)
        out, current = [], first
        while current <= self.window_end.date():
            out.append(current)
            current = date(current.year + current.month // 12, current.month % 12 + 1, 1)
        return out

    def fetch(self) -> list[RawEvent]:
        seen: dict[int, dict[str, Any]] = {}
        for month in self.months():
            params = {"type": "month", "sport": 0, "location": "all", "date": f"{month.month}/1/{month.year}"}
            for day in self.http.get_json(FEED_URL, params=params) or []:
                for event in day.get("events") or []:
                    seen.setdefault(event["id"], event)
        return [self.raw(e["id"], e, f"{BASE}/calendar") for e in seen.values()]

    def parse(self, raw: RawEvent) -> list[Event]:
        d = raw.raw_data
        if not is_home(d):
            return []  # away games in other states are not local events
        if re.search(r"cancel|postpon", d.get("noplay_text") or "", re.I):
            return []

        sport = d["sport"]["title"]
        opponent_raw = (d.get("opponent") or {}).get("title") or ""
        opponent = _RANK.sub("", opponent_raw).strip()
        at_vs = d.get("at_vs") or "vs"
        title = f"Maryland {sport} {at_vs} {opponent}" if opponent else f"Maryland {sport}"

        time_text = (d.get("time") or "").strip()
        start_of_day = parse_datetime(d["date"][:10])
        clock = parse_time_of_day(time_text) if time_text and not re.match(r"tba|tbd|all day", time_text, re.I) else None
        start = start_of_day.replace(hour=clock.hour, minute=clock.minute) if clock else start_of_day

        media = d.get("media") or {}
        tickets = (media.get("tickets") or {}).get("url")
        result = d.get("result") or {}
        result_text = None
        if result.get("status"):
            result_text = f"{result['status']} {result.get('team_score')}-{result.get('opponent_score')}"
        links = [(result.get("boxscore") or {}).get("url"), (media.get("preview") or {}).get("url")]
        page = next((clean_url(u, BASE) for u in links if u), None)
        facility = (d.get("facility") or {}).get("title") or default_venue(sport)

        return [
            self.event(
                source_event_id=raw.source_event_id,
                source_url=page or f"{BASE}/calendar",
                title=title,
                summary=f"{sport}: Maryland {at_vs} {opponent_raw}".strip() + (" (Big Ten)" if d.get("conference") else ""),
                start_time=start,
                all_day=clock is None,
                venue_name=facility or d.get("location"),
                address=d.get("location") or "College Park, MD",
                organizer_name="Maryland Athletics",
                registration_url=clean_url(tickets),
                is_umd=True,
                event_type="sports_game",
                tags=["sports"],
                source_categories=[sport],
                extra={
                    "sport": sport,
                    "home_team": "Maryland",
                    "away_team": opponent,
                    "opponent": opponent_raw,
                    "home_away": "home" if d.get("location_indicator") == "H" else "neutral",
                    "conference_game": bool(d.get("conference")),
                    "result_if_completed": result_text,
                    "ticket_url": clean_url(tickets),
                    "tournament": (d.get("tournament") or {}).get("title") if isinstance(d.get("tournament"), dict) else None,
                    "watch_url": (media.get("video") or {}).get("url"),
                },
            )
        ]
