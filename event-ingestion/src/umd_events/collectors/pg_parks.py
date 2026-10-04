"""Prince George's County Parks (pgparks.com, WordPress + The Events Calendar REST API).

The county runs hundreds of events; only facilities close to College Park are collected. The API leaves
``venue`` empty, so each facility tag maps to a known venue.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from ..models import Event, RawEvent
from ..normalize.text import html_to_text, summarize
from ..normalize.times import ensure_eastern
from .base import BaseCollector, register

API_URL = "https://www.pgparks.com/wp-json/tribe/events/v1/events"

# Facility tag slug -> (venue name, address)
NEARBY_FACILITIES: dict[str, tuple[str, str]] = {
    "college-park-aviation-museum": ("College Park Aviation Museum", "1985 Corporal Frank Scott Dr, College Park, MD 20740"),
    "riversdale-events": ("Riversdale House Museum", "4811 Riverdale Rd, Riverdale Park, MD 20737"),
    "bladensburg-waterfront-events": ("Bladensburg Waterfront Park", "4601 Annapolis Rd, Bladensburg, MD 20710"),
    "brentwood-arts-exchange": ("Brentwood Arts Exchange", "3901 Rhode Island Ave, Brentwood, MD 20722"),
    "live-well-langley": ("Langley Park Community Center", "1500 Merrimac Dr, Hyattsville, MD 20783"),
}
AGE_CATEGORIES = {"youth", "teens", "adults", "seniors", "all ages", "family", "preschool", "children"}


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    return ensure_eastern(datetime.fromisoformat(value).replace(tzinfo=timezone.utc))


@register
class PGParksCollector(BaseCollector):
    source_name = "pg_parks"
    display_name = "Prince George's County Parks"
    scraper_version = "1"
    tier = 2

    def fetch(self) -> list[RawEvent]:
        raws: dict[str, RawEvent] = {}
        for tag in NEARBY_FACILITIES:
            page = 1
            while True:
                params = {
                    "per_page": 50,
                    "page": page,
                    "tags": tag,
                    "start_date": self.now.strftime("%Y-%m-%d"),
                    "end_date": self.window_end.strftime("%Y-%m-%d"),
                }
                try:
                    data = self.http.get_json(API_URL, params=params, headers={"Accept": "application/json"})
                except Exception:  # the API returns 400 for a page past the end
                    if page == 1:
                        raise
                    break
                for event in data.get("events") or []:
                    key = str(event["id"])
                    if key not in raws:
                        raws[key] = self.raw(key, {**event, "_facility_tag": tag}, event.get("url"))
                if page >= (data.get("total_pages") or 1):
                    break
                page += 1
        return list(raws.values())

    def parse(self, raw: RawEvent) -> list[Event]:
        d = raw.raw_data
        if d.get("status") != "publish" or d.get("hide_from_listings"):
            return []
        venue, address = NEARBY_FACILITIES.get(d.get("_facility_tag"), (None, None))
        categories = [html.unescape(c["name"]) for c in d.get("categories") or []]
        cost = d.get("cost_details") or {}
        values = [float(v) for v in cost.get("values") or [] if str(v).replace(".", "", 1).isdigit()]
        cost_text = (d.get("cost") or "").strip()
        is_free = "free" in cost_text.lower() or "Free" in categories or (bool(values) and max(values) == 0)
        description = html_to_text(d.get("description"))
        image = (d.get("image") or {}) if isinstance(d.get("image"), dict) else {}
        large = ((image.get("sizes") or {}).get("large") or {}).get("url") or image.get("url")
        return [
            self.event(
                source_event_id=raw.source_event_id,
                source_url=d["url"],
                title=html.unescape(d["title"]),
                summary=summarize(html_to_text(d.get("excerpt"))) or summarize(description),
                description=description,
                start_time=parse_utc(d.get("utc_start_date")),
                end_time=parse_utc(d.get("utc_end_date")),
                all_day=bool(d.get("all_day")),
                venue_name=venue,
                address=address,
                organizer_name="Prince George's County Parks and Recreation",
                image_url=large,
                registration_url=d.get("website") or d["url"],
                price_min=min(values) if values else (0.0 if is_free else None),
                price_max=max(values) if values else (0.0 if is_free else None),
                is_free=is_free if (values or cost_text or "Free" in categories) else None,
                is_umd=False,
                is_online=bool(d.get("is_virtual")),
                source_categories=categories,
                extra={
                    "age_range": [c for c in categories if c.lower() in AGE_CATEGORIES],
                    "price_text": cost_text or None,
                    "facility_tag": d.get("_facility_tag"),
                },
            )
        ]
