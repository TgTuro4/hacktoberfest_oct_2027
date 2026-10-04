"""Ticketmaster Discovery API v2: concerts, comedy, sports and theater near College Park.

Needs a free API key from developer.ticketmaster.com (TICKETMASTER_API_KEY). Skipped when it is not set.
"""

from __future__ import annotations

from datetime import date, timezone
from typing import Any

from ..config import UMD_CENTER
from ..models import Event, RawEvent
from ..normalize.text import html_to_text, summarize
from ..normalize.times import combine, parse_datetime, parse_time_of_day
from ..normalize.urls import clean_url
from .base import BaseCollector, register

API_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
PAGE_SIZE = 200  # API maximum; deep paging is capped at size * page < 1000


def best_image(images: list[dict[str, Any]]) -> str | None:
    wide = [i for i in images if i.get("ratio") == "16_9" and i.get("url")]
    pool = wide or [i for i in images if i.get("url")]
    return max(pool, key=lambda i: i.get("width") or 0)["url"] if pool else None


@register
class TicketmasterCollector(BaseCollector):
    source_name = "ticketmaster"
    display_name = "Ticketmaster"
    scraper_version = "1"
    tier = 2

    def skip_reason(self) -> str | None:
        return None if self.settings.ticketmaster_api_key else "TICKETMASTER_API_KEY is not set"

    def fetch(self) -> list[RawEvent]:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        raws = []
        for page in range(1000 // PAGE_SIZE):
            params = {
                "apikey": self.settings.ticketmaster_api_key,
                "latlong": f"{UMD_CENTER[0]},{UMD_CENTER[1]}",
                "radius": self.settings.ticketmaster_radius_miles,
                "unit": "miles",
                "startDateTime": self.now.astimezone(timezone.utc).strftime(fmt),
                "endDateTime": self.window_end.astimezone(timezone.utc).strftime(fmt),
                "size": PAGE_SIZE,
                "page": page,
                "sort": "date,asc",
                "locale": "*",
            }
            data = self.http.get_json(API_URL, params=params)
            events = (data.get("_embedded") or {}).get("events") or []
            raws.extend(self.raw(e["id"], e, e.get("url")) for e in events)
            if page + 1 >= (data.get("page") or {}).get("totalPages", 0):
                break
        return raws

    def parse(self, raw: RawEvent) -> list[Event]:
        d = raw.raw_data
        dates = d.get("dates") or {}
        start_info = dates.get("start") or {}
        status = ((dates.get("status") or {}).get("code") or "").lower()
        if status in ("cancelled", "canceled", "postponed"):
            return []
        if start_info.get("dateTime"):
            start, all_day = parse_datetime(start_info["dateTime"]), False
        else:
            clock = parse_time_of_day(start_info["localTime"]) if start_info.get("localTime") else None
            start, all_day = combine(date.fromisoformat(start_info["localDate"]), clock), clock is None

        venue = ((d.get("_embedded") or {}).get("venues") or [{}])[0]
        location = venue.get("location") or {}
        address = ", ".join(filter(None, [
            (venue.get("address") or {}).get("line1"),
            (venue.get("city") or {}).get("name"),
            " ".join(filter(None, [(venue.get("state") or {}).get("stateCode"), venue.get("postalCode")])),
        ]))
        prices = d.get("priceRanges") or []
        price_min = min((p["min"] for p in prices if p.get("min") is not None), default=None)
        price_max = max((p["max"] for p in prices if p.get("max") is not None), default=None)
        categories = []
        for c in d.get("classifications") or []:
            for level in ("segment", "genre", "subGenre"):
                name = (c.get(level) or {}).get("name")
                if name and name != "Undefined":
                    categories.append(name)
        description = html_to_text(d.get("info") or d.get("description") or d.get("pleaseNote"))
        promoter = (d.get("promoter") or {}).get("name")

        return [
            self.event(
                source_event_id=raw.source_event_id,
                source_url=clean_url(d["url"]),
                title=d["name"],
                description=description,
                summary=summarize(description),
                start_time=start,
                all_day=all_day,
                venue_name=venue.get("name"),
                address=address or None,
                latitude=float(location["latitude"]) if location.get("latitude") else None,
                longitude=float(location["longitude"]) if location.get("longitude") else None,
                organizer_name=promoter or venue.get("name"),
                image_url=best_image(d.get("images") or []),
                registration_url=clean_url(d["url"]),
                price_min=price_min,
                price_max=price_max,
                is_free=(price_max == 0) if price_max is not None else None,
                is_umd=False,  # set from the resolved venue during normalization
                event_type="sports_game" if "Sports" in categories else "performance",
                source_categories=categories,
                extra={"segment": categories[0] if categories else None, "ticket_status": status or None},
            )
        ]
