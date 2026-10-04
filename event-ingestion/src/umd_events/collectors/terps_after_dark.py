"""Terps After Dark (terpsafterdark.umd.edu, Drupal).

The site lists the current weeks' events as cards that usually link to a TerpLink event. Cards are scraped
from the site; linked TerpLink events are read from the TerpLink API for exact times. Every TerpLink event
in the hidden "Terps After Dark" category is collected too.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from bs4 import BeautifulSoup

from ..models import Event, RawEvent
from ..normalize.text import clean_text, summarize
from ..normalize.times import combine, find_date, parse_time_range
from ..normalize.titles import normalize_title
from ..normalize.urls import clean_url
from . import terplink
from .base import BaseCollector, register

SITE_URL = "https://terpsafterdark.umd.edu/"
TAD_CATEGORY_ID = "13847"
_TERPLINK_EVENT = re.compile(r"terplink\.umd\.edu/event/(\d+)")


def extract_cards(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    cards = []
    for card in soup.select(".col-800"):
        strongs = [clean_text(s.get_text(" ", strip=True)) for s in card.find_all("strong")]
        strongs = [s for s in strongs if s]
        if not strongs:
            continue
        date_line = next((s for s in strongs if find_date(s)), None)
        time_line = next((s for s in strongs if re.search(r"\d\s*(?:a\.?m|p\.?m)|noon", s, re.I)), None)
        if not date_line:
            continue
        presenter = next((clean_text(e.get_text(" ", strip=True)) for e in card.find_all("em")
                          if "presented by" in e.get_text().lower()), None)
        paragraphs = [clean_text(p.get_text(" ", strip=True)) for p in card.find_all("p") if not p.find("strong")]
        description = max((p for p in paragraphs if p and not p.lower().startswith("learn more")), key=len, default=None)
        link = card.find("a", href=_TERPLINK_EVENT) or card.find("a", href=True)
        image = card.find("img", src=True)
        cards.append({
            "title": strongs[0],
            "date_text": date_line,
            "time_text": time_line,
            "presenter": re.sub(r"(?i)^presented by\s+(the\s+)?", "", presenter).strip() if presenter else None,
            "description": description,
            "image": clean_url(image["src"], SITE_URL) if image else None,
            "image_alt": image.get("alt") if image else None,
            "link": clean_url(link["href"], SITE_URL) if link else None,
            "terplink_id": (_TERPLINK_EVENT.search(link["href"]).group(1)
                            if link and _TERPLINK_EVENT.search(link["href"]) else None),
        })
    return cards


@register
class TerpsAfterDarkCollector(BaseCollector):
    source_name = "terps_after_dark"
    display_name = "Terps After Dark"
    scraper_version = "1"

    def fetch(self) -> list[RawEvent]:
        raws: dict[str, RawEvent] = {}
        for card in extract_cards(self.http.get_text(SITE_URL)):
            if card["terplink_id"]:
                card["terplink"] = terplink.fetch_detail(self.http, card["terplink_id"], expire_after=6 * 3600)
            key = card["terplink_id"] or f"site:{normalize_title(card['title']).replace(' ', '-')}:{card['date_text']}"
            raws[key] = self.raw(key, {"kind": "card", **card}, card["link"] or SITE_URL)

        records = terplink.search_events(self.http, self.now.isoformat(), self.window_end.isoformat(),
                                         {"categoryIds[0]": TAD_CATEGORY_ID})
        for record in records:
            key = str(record["id"])
            if key not in raws:
                raws[key] = self.raw(key, {"kind": "terplink", **terplink.scrub(record)}, terplink.event_url(key))
        return list(raws.values())

    def parse(self, raw: RawEvent) -> list[Event]:
        d = raw.raw_data
        tags = ["nightlife", "social"]
        if d["kind"] == "terplink":
            return [self.event(**terplink.event_fields(d), tags=tags)] if terplink.is_public(d) else []

        detail = d.get("terplink")
        if detail and detail.get("startsOn"):
            fields = terplink.event_fields(detail)
            fields["organizer_name"] = d.get("presenter") or fields["organizer_name"]
            fields["image_url"] = fields["image_url"] or d.get("image")
            fields["description"] = fields["description"] or d.get("description")
            return [self.event(**fields, tags=tags)]

        day = find_date(d["date_text"])
        start_clock, end_clock = parse_time_range(d.get("time_text") or "")
        end = combine(day, end_clock) if end_clock else None
        if end and start_clock and end_clock <= start_clock:  # "10 p.m. to midnight"
            end += timedelta(days=1)
        venue = None
        if d.get("time_text") and " in " in d["time_text"]:
            venue = d["time_text"].split(" in ", 1)[1].strip(" .")
        return [
            self.event(
                source_event_id=raw.source_event_id,
                source_url=d.get("link") or SITE_URL,
                title=d["title"],
                description=d.get("description"),
                summary=summarize(d.get("description")),
                start_time=combine(day, start_clock),
                end_time=end,
                all_day=start_clock is None,
                venue_name=venue,
                organizer_name=d.get("presenter") or "Terps After Dark",
                image_url=d.get("image"),
                registration_url=d.get("link"),
                is_umd=True,
                tags=tags,
                external_refs={"terplink": d["terplink_id"]} if d.get("terplink_id") else {},
            )
        ]
