"""Student Entertainment Events (SEE).

SEE posts its events to TerpLink (organization 278293), which is the structured source used here. The
see.umd.edu Wix site has one hand-built page per marquee event (comedy show, concert, lecture). Those pages
are parsed best-effort for date, time, venue and price; pages without a parseable future date are skipped.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..models import Event, RawEvent
from ..normalize.prices import parse_price
from ..normalize.text import clean_text, summarize
from ..normalize.times import combine, find_date, parse_time_of_day
from ..normalize.urls import clean_url
from . import terplink
from .base import BaseCollector, register

SITE = "https://www.see.umd.edu"
SEE_ORG_ID = "278293"
NON_EVENT_PAGES = {
    "", "events", "about-1", "about", "booking", "contact", "exec-board", "funding", "getinvolved", "payroll",
    "press", "promo", "sfb", "sponsors", "seestory", "cinema", "comedy", "concert", "lectures",
    "performing-arts", "blog", "doc",
}


def page_lines(html: str) -> tuple[str | None, list[str], BeautifulSoup]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    if title:
        title = re.sub(r"\s*(?:[|\-–—]\s*)?seeumd\s*$", "", title, flags=re.I).strip()
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    start = text.find("Use tab to navigate through the menu items.")
    end = text.rfind("Contact\nOffice Phone")
    body = text[start + 43 if start >= 0 else 0: end if end > 0 else None]
    lines = [clean_text(line) for line in body.split("\n")]
    return title, [line for line in lines if line], soup


def extract_event_page(html: str, url: str) -> dict[str, Any] | None:
    title, lines, soup = page_lines(html)
    date_line = next((line for line in lines if find_date(line) and re.search(r"20\d\d|when", line, re.I)), None)
    date_line = date_line or next((line for line in lines if find_date(line)), None)
    if not title or not date_line:
        return None
    time_line = next((line for line in lines if re.search(r"(event )?starts?\b.*\d", line, re.I)), None)
    time_line = time_line or (date_line if re.search(r"\d\s*(?:am|pm|a\.m|p\.m)", date_line, re.I) else None)
    time_line = time_line or next((line for line in lines if re.search(r"\b\d{1,2}(:\d\d)?\s*(am|pm)\b", line, re.I)), None)
    venue_line = next((line for line in lines if line.startswith("📍") or re.match(r"^•?\s*where\s*:", line, re.I)), None)
    price_lines = [line for line in lines if "$" in line or re.search(r"free of charge|free admission", line, re.I)]
    description = None
    if "Event Description" in lines:
        idx = lines.index("Event Description")
        description = "\n".join(lines[idx + 1: idx + 4])
    else:
        description = max((line for line in lines if len(line) > 120), key=len, default=None)
    og_image = soup.find("meta", property="og:image")
    ticket = next((a["href"] for a in soup.find_all("a", href=True) if "ticket" in a.get_text(" ").lower()), None)
    return {
        "url": url,
        "title": title,
        "date_text": date_line,
        "time_text": time_line,
        "venue_text": venue_line,
        "price_text": " ".join(price_lines) or None,
        "description": description,
        "image": og_image["content"] if og_image and og_image.get("content") else None,
        "ticket_url": ticket,
    }


def time_from(text: str | None):
    if not text:
        return None
    starts = re.search(r"starts?\s*(?:at\s*)?(\d{1,2}(?::\d\d)?\s*(?:a\.?m\.?|p\.?m\.?))", text, re.I)
    if starts:
        return parse_time_of_day(starts.group(1))
    any_time = re.search(r"\b(\d{1,2}(?::\d\d)?\s*(?:a\.?m\.?|p\.?m\.?))", text, re.I)
    return parse_time_of_day(any_time.group(1)) if any_time else None


@register
class SEECollector(BaseCollector):
    source_name = "see"
    display_name = "Student Entertainment Events"
    scraper_version = "1"

    def fetch(self) -> list[RawEvent]:
        raws = []
        for record in terplink.search_events(self.http, self.now.isoformat(), self.window_end.isoformat(),
                                             {"organizationIds[0]": SEE_ORG_ID}):
            raws.append(self.raw(record["id"], {"kind": "terplink", **terplink.scrub(record)},
                                 terplink.event_url(record["id"])))

        events_page = BeautifulSoup(self.http.get_text(f"{SITE}/events"), "lxml")
        pages = set()
        for a in events_page.find_all("a", href=True):
            href = clean_url(a["href"], SITE)
            if href and urlparse(href).netloc.endswith("see.umd.edu"):
                slug = urlparse(href).path.strip("/")
                if slug not in NON_EVENT_PAGES and "/" not in slug:
                    pages.add(href)
        for url in sorted(pages):
            page = extract_event_page(self.http.get_text(url, expire_after=12 * 3600), url)
            if page:
                raws.append(self.raw(f"site:{urlparse(url).path.strip('/')}", {"kind": "site", **page}, url))
        return raws

    def parse(self, raw: RawEvent) -> list[Event]:
        d = raw.raw_data
        if d["kind"] == "terplink":
            return [self.event(**terplink.event_fields(d))] if terplink.is_public(d) else []

        day = find_date(d["date_text"])
        clock = time_from(d.get("time_text"))
        venue = re.sub(r"^(?:📍|•?\s*where\s*:)\s*", "", d["venue_text"] or "", flags=re.I).strip(" .") or None
        price_min, price_max, is_free = parse_price(d.get("price_text"))
        return [
            self.event(
                source_event_id=raw.source_event_id,
                source_url=d["url"],
                title=re.sub(r"\s+20\d\d$", "", d["title"]),
                description=d.get("description"),
                summary=summarize(d.get("description")),
                start_time=combine(day, clock),
                all_day=clock is None,
                venue_name=venue,
                organizer_name="Student Entertainment Events",
                image_url=d.get("image"),
                registration_url=clean_url(d.get("ticket_url")) or d["url"],
                price_min=price_min,
                price_max=price_max,
                is_free=is_free,
                is_umd=True,
                extra={"price_text": d.get("price_text")},
            )
        ]
