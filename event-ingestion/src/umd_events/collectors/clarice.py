"""The Clarice Smith Performing Arts Center (Drupal). Walks the month calendar, then reads each event page."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..models import Event, RawEvent
from ..normalize.prices import parse_price
from ..normalize.text import clean_text, html_to_text, summarize
from ..normalize.times import combine, parse_datetime, parse_time_of_day
from ..normalize.urls import clean_url
from .base import BaseCollector, register

log = logging.getLogger(__name__)

BASE = "https://theclarice.umd.edu"
CALENDAR_URL = f"{BASE}/events/calendar"
VENUE = "The Clarice Smith Performing Arts Center"


def extract_calendar(html: str) -> tuple[list[dict[str, Any]], str | None]:
    """Return the occurrences on one month grid and the link to the next month."""
    soup = BeautifulSoup(html, "lxml")
    occurrences = []
    for cell in soup.select("td[data-calendar-view-year][data-calendar-view-month][data-calendar-view-day]"):
        try:
            day = date(2000 + int(cell["data-calendar-view-year"]), int(cell["data-calendar-view-month"]),
                       int(cell["data-calendar-view-day"]))
        except ValueError:
            continue
        for row in cell.select("li.calendar-view-day__row"):
            link = row.select_one(".event-calendar-item__title a[href]")
            if not link:
                continue
            time_el = row.select_one(".event-result-card__date-time")
            presents = row.select_one("[class*=calendar-item__presents]")
            occurrences.append({
                "url": urljoin(BASE, link["href"]),
                "title": clean_text(link.get_text(" ", strip=True)),
                "date": day.isoformat(),
                "time": clean_text(time_el.get_text(" ", strip=True)) if time_el else None,
                "presenter": clean_text(presents.get_text(" ", strip=True)) if presents else None,
            })
    nxt = soup.select_one(".calendar-view-pager .pager__next a[href], .pager__item--next a[href]")
    return occurrences, (urljoin(CALENDAR_URL, nxt["href"]) if nxt else None)


def extract_detail(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    text = lambda sel: clean_text(soup.select_one(sel).get_text(" ", strip=True)) if soup.select_one(sel) else None  # noqa: E731
    glance = {}
    for section in soup.select(".event-hero__at-a-glance-section"):
        label = section.select_one(".event-hero__at-a-glance-section-label")
        content = section.select_one(".event-hero__at-a-glance-section-content")
        if label and content:
            glance[clean_text(label.get_text(" ", strip=True)).lower()] = clean_text(content.get_text(" ", strip=True))
    description = None
    heading = soup.find(["h2", "h3"], string=re.compile(r"About the Event", re.I))
    if heading:
        parts = [str(sib) for sib in heading.find_next_siblings()]
        description = html_to_text("".join(parts))
    image = soup.select_one(".event-hero__image img[src]")
    performances = []
    for t in soup.select("time.event-performance-dates__event-time[datetime]"):
        row = t.find_parent(class_="performanceRow")
        location = row.select_one(".location") if row else None
        performances.append({
            "datetime": t["datetime"],
            "location": clean_text(location.get_text(" ", strip=True)) if location else None,
        })
    venue = glance.get("venue")
    if venue:  # drop seating notes: "Dekelboum Concert Hall, ... General Admission"
        venue = re.sub(r"\s*(General Admission|Reserved\b.*|Open Seating.*|Festival Seating.*)$", "", venue, flags=re.I)
    return {
        "title": text(".event-hero__title"),
        "presents": text(".event-hero__presents"),
        "subtitle": text(".event-hero__subtitle"),
        "intro": text(".event-hero__intro-content"),
        "image_url": urljoin(BASE, image["src"]) if image else None,
        "price": glance.get("price"),
        "venue": venue or None,
        "description": description,
        "performances": performances,
    }


@register
class ClariceCollector(BaseCollector):
    source_name = "clarice"
    display_name = "The Clarice"
    scraper_version = "1"

    def fetch(self) -> list[RawEvent]:
        occurrences: list[dict[str, Any]] = []
        url: str | None = CALENDAR_URL
        months = max(1, round(self.settings.horizon_days / 30) + 1)
        for _ in range(months):
            if not url:
                break
            found, url = extract_calendar(self.http.get_text(url))
            occurrences.extend(found)

        by_url: dict[str, list[dict[str, Any]]] = {}
        for occ in occurrences:
            by_url.setdefault(occ["url"], []).append(occ)

        raws = []
        for page_url, occs in by_url.items():
            try:
                detail = extract_detail(self.http.get_text(page_url, expire_after=24 * 3600))
            except Exception as exc:
                log.warning("[clarice] detail failed for %s: %s", page_url, exc)
                detail = {}
            slug = urlparse(page_url).path.rstrip("/").split("/")[-1]
            raws.append(self.raw(slug, {"url": page_url, "occurrences": occs, "detail": detail}, page_url))
        return raws

    def parse(self, raw: RawEvent) -> list[Event]:
        d = raw.raw_data
        detail = d.get("detail") or {}
        title = detail.get("title") or d["occurrences"][0]["title"]
        presenter = detail.get("presents") or d["occurrences"][0].get("presenter")
        price_min, price_max, is_free = parse_price(detail.get("price"))
        description = detail.get("description") or detail.get("intro")

        starts: list[tuple[Any, str | None]] = []
        for perf in detail.get("performances") or []:
            starts.append((parse_datetime(perf["datetime"]), perf.get("location")))
        if not starts:  # festival pages etc. have no performance list; fall back to the calendar grid
            for occ in d["occurrences"]:
                clock = parse_time_of_day(occ["time"]) if occ.get("time") else None
                starts.append((combine(date.fromisoformat(occ["date"]), clock), None))

        events = []
        for start, room in dict.fromkeys(starts):
            venue = detail.get("venue") or (f"{room}, {VENUE}" if room else VENUE)
            events.append(
                self.event(
                    source_event_id=f"{raw.source_event_id}:{start:%Y%m%dT%H%M}",
                    source_url=d["url"],
                    title=title,
                    summary=summarize(detail.get("intro")) or summarize(description),
                    description=description,
                    start_time=start,
                    venue_name=venue,
                    address="8270 Alumni Dr, College Park, MD 20742",
                    organizer_name=presenter or VENUE,
                    image_url=clean_url(detail.get("image_url")),
                    registration_url=d["url"],
                    price_min=price_min,
                    price_max=price_max,
                    is_free=is_free,
                    is_umd=True,
                    event_type="performance",
                    source_categories=[c for c in [presenter] if c],
                    extra={"presenter": presenter, "price_text": detail.get("price"), "subtitle": detail.get("subtitle")},
                )
            )
        return events
