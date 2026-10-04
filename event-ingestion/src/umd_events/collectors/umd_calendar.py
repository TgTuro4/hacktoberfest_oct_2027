"""UMD campus calendar (calendar.umd.edu).

The site is Craft CMS + Solspace Calendar. Its search page loads events from a public GraphQL endpoint with
a read-only token embedded in the page's JavaScript. This collector uses that endpoint for the event list,
then reads each event's detail page once (cached) for the venue, ticket link and hosts, which the public
GraphQL schema does not expose.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

from bs4 import BeautifulSoup

from ..models import Event, RawEvent
from ..normalize.text import clean_text, html_to_text, summarize
from ..normalize.times import fix_recurring_end, parse_floating
from ..normalize.urls import clean_url
from .base import BaseCollector, register

log = logging.getLogger(__name__)

BASE = "https://calendar.umd.edu"
GRAPHQL_URL = f"{BASE}/graphql"
# Public token shipped in calendar.umd.edu/search.*.js. Rediscovered at runtime in case it rotates.
FALLBACK_TOKEN = "ty5hts_R6EWaNT8zBYqVT8edynE0f9cK"

_FIELDS = """
  id title url slug startDate endDate allDay multiDay rrule
  summary: commonRichTextTwo description: commonRichText
  locationType: calendarLocationType venueDescription: calendarVenueDescription
  offCampusTitle: calendarOffCampusTitle offCampusLink: calendarOffCampusLink
  building: categoriesCampusBuildingSingle { title }
  address: commonAddress { ... on address_Entry { street1 street2 city state zipCode } }
  image: commonAssetHeroImageSingle { url }
  audience: categoryAudienceMultiple { title }
  status: categoriesEventStatus { title slug }
  topics: categoriesEventTypeMultiple { title }
  units: categoryCampusUnitsMultiple { title }
  tags: categoryTagsMultiple { title }
"""
QUERY = (
    "query EventSearch($offset: Int!, $limit: Int!, $startDate: String!, $endDate: String) {"
    " solspace_calendar { events(limit: $limit, offset: $offset, rangeStart: $startDate, rangeEnd: $endDate,"
    " loadOccurrences: true) {"
    f" ... on communications_Event {{ {_FIELDS} }} ... on submission_Event {{ {_FIELDS} }} }} }} }}"
)


def extract_detail(html: str) -> dict[str, Any]:
    """Pull venue, address, ticket link and hosts from an event detail page."""
    soup = BeautifulSoup(html, "lxml")
    detail: dict[str, Any] = {}
    location = soup.find("umd-event-location")
    if location:
        title = location.find(["h3", "h4"])
        detail["venue"] = clean_text(title.get_text(" ", strip=True)) if title else None
        address = location.find("address")
        if address:
            lines = [clean_text(span.get_text(" ", strip=True)) for span in address.find_all("span")]
            detail["address"] = ", ".join(filter(None, lines)) or clean_text(address.get_text(" ", strip=True))
    link = soup.select_one(".event-links a.call-to-action-block[href]")
    if link:
        detail["ticket_url"] = clean_url(link["href"], BASE)
        detail["ticket_label"] = clean_text(link.get_text(" ", strip=True))
    hosts = [clean_text(span.get_text(" ", strip=True)) for span in soup.select("umd-event-hosts .host-item span")]
    detail["hosts"] = [h for h in hosts if h]
    return detail


@register
class UMDCalendarCollector(BaseCollector):
    source_name = "umd_calendar"
    display_name = "UMD Campus Calendar"
    scraper_version = "1"

    page_size = 100

    def discover_token(self) -> str:
        if self.settings.umd_calendar_token:
            return self.settings.umd_calendar_token
        try:
            page = self.http.get_text(f"{BASE}/search", expire_after=24 * 3600)
            script = re.search(r'src="(/search\.[A-Za-z0-9_-]+\.js)', page)
            if script:
                js = self.http.get_text(BASE + script.group(1), expire_after=24 * 3600)
                token = re.search(r"Bearer ([A-Za-z0-9_\-]{16,})", js)
                if token:
                    return token.group(1)
        except Exception as exc:
            log.warning("[umd_calendar] token discovery failed, using fallback: %s", exc)
        return FALLBACK_TOKEN

    def fetch(self) -> list[RawEvent]:
        headers = {"Authorization": f"Bearer {self.discover_token()}", "Content-Type": "application/json"}
        records: list[dict[str, Any]] = []
        offset = 0
        while True:
            variables = {
                "offset": offset,
                "limit": self.page_size,
                "startDate": self.now.strftime("%Y-%m-%d"),
                "endDate": self.window_end.strftime("%Y-%m-%d"),
            }
            data = self.http.post(GRAPHQL_URL, json={"query": QUERY, "variables": variables}, headers=headers).json()
            if data.get("errors"):
                raise RuntimeError(f"GraphQL errors: {data['errors']}")
            batch = [e for e in data["data"]["solspace_calendar"]["events"] if e]
            records.extend(batch)
            if len(batch) < self.page_size or offset > 5000:
                break
            offset += self.page_size

        details = self.fetch_details(records) if self.settings.umd_calendar_fetch_details else {}

        raws = []
        for record in records:
            occurrence = f"{record['id']}:{record['startDate'][:16]}"
            data = {**record, "_detail": details.get(record["id"], {})}
            raws.append(self.raw(occurrence, data, record.get("url")))
        return raws

    def fetch_details(self, records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        """Venue/ticket/host details from event pages.

        Uncached pages take the site ~8s to render, so only in-person events in the next
        ``umd_calendar_detail_days`` are enriched, soonest first, at most ``umd_calendar_max_detail_fetches``
        new pages per run, a few in parallel. Pages are cached for a week, so later runs fill in the rest.
        """
        ttl = self.settings.detail_cache_ttl_s
        cutoff = (self.now + timedelta(days=self.settings.umd_calendar_detail_days)).strftime("%Y-%m-%d")
        wanted: dict[int, str] = {}
        for record in sorted(records, key=lambda r: r["startDate"]):
            online_only = (record.get("locationType") or []) == ["online"]
            if record.get("url") and not online_only and record["startDate"][:10] <= cutoff:
                wanted.setdefault(record["id"], record["url"])

        details: dict[int, dict[str, Any]] = {}
        missing: list[tuple[int, str]] = []
        for event_id, url in wanted.items():
            html = self.http.cached_text(url, expire_after=ttl)
            if html is None:
                missing.append((event_id, url))
            else:
                details[event_id] = extract_detail(html)

        def load(item: tuple[int, str]) -> tuple[int, dict[str, Any]]:
            event_id, url = item
            try:
                return event_id, extract_detail(self.http.get_text(url, expire_after=ttl))
            except Exception as exc:
                log.warning("[umd_calendar] detail page failed for %s: %s", url, exc)
                return event_id, {}

        batch = missing[: self.settings.umd_calendar_max_detail_fetches]
        with ThreadPoolExecutor(max_workers=max(1, self.settings.detail_workers)) as pool:
            details.update(pool.map(load, batch))
        log.info("[umd_calendar] details: %d cached, %d fetched, %d deferred to a later run",
                 len(wanted) - len(missing), len(batch), len(missing) - len(batch))
        return details

    def parse(self, raw: RawEvent) -> list[Event]:
        d = raw.raw_data
        detail = d.get("_detail") or {}
        if any("cancel" in (s.get("slug") or "") or "postpon" in (s.get("slug") or "") for s in d.get("status") or []):
            return []

        start = parse_floating(d["startDate"])
        end = parse_floating(d.get("endDate"))
        if d.get("rrule"):
            end = fix_recurring_end(start, end)

        location_types = d.get("locationType") or []
        address_entry = next((a for a in d.get("address") or [] if a), None)
        address = None
        if address_entry:
            address = ", ".join(filter(None, [address_entry.get("street1"), address_entry.get("street2"),
                                              address_entry.get("city"),
                                              " ".join(filter(None, [address_entry.get("state"), address_entry.get("zipCode")]))]))
        building = next((b.get("title") for b in d.get("building") or [] if b), None)
        venue = detail.get("venue") or d.get("offCampusTitle") or building
        is_online = "online" in location_types and "on_campus" not in location_types and "off_campus" not in location_types
        if not venue and is_online:
            venue = "Online"

        description = html_to_text(d.get("description")) or html_to_text(d.get("summary"))
        units = [u["title"] for u in d.get("units") or [] if u]
        hosts = detail.get("hosts") or units
        topics = [t["title"] for t in d.get("topics") or [] if t]
        tags = [t["title"] for t in d.get("tags") or [] if t]

        return [
            self.event(
                source_event_id=raw.source_event_id,
                source_url=f"{d['url']}?start={start:%Y-%m-%d}",
                title=d["title"],
                summary=summarize(html_to_text(d.get("summary"))) or summarize(description),
                description=description,
                start_time=start,
                end_time=end,
                all_day=bool(d.get("allDay")),
                venue_name=venue,
                address=detail.get("address") or address,
                organizer_name=hosts[0] if hosts else None,
                image_url=next((i["url"] for i in d.get("image") or [] if i and i.get("url")), None),
                registration_url=detail.get("ticket_url") or clean_url(d.get("offCampusLink")),
                is_umd=True,
                is_online=is_online,
                source_categories=topics + tags,
                extra={
                    "audiences": [a["title"] for a in d.get("audience") or [] if a],
                    "host_departments": hosts,
                    "event_topics": topics,
                    "location_type": location_types,
                    "venue_note": html_to_text(d.get("venueDescription")),
                    "ticket_label": detail.get("ticket_label"),
                    "calendar_event_id": d["id"],
                },
            )
        ]
