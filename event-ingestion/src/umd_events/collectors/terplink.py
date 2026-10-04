"""TerpLink (Campus Labs Engage). Uses the public JSON discovery API that terplink.umd.edu/events calls."""

from __future__ import annotations

import logging
from typing import Any

from ..http import HttpClient
from ..models import Event, RawEvent
from ..normalize.text import html_to_text, summarize
from ..normalize.times import parse_datetime
from ..normalize.venues import ONLINE_PATTERN
from .base import BaseCollector, register

log = logging.getLogger(__name__)

BASE = "https://terplink.umd.edu"
SEARCH_URL = f"{BASE}/api/discovery/event/search"
DETAIL_URL = f"{BASE}/api/discovery/event/{{id}}"
IMAGE_URL = "https://se-images.campuslabs.com/clink/images/{path}?preset=med-w"
# Engage "branches": student organizations vs. university departments/offices.
STUDENT_ORG_BRANCH_ID = 226014

# Fields that identify the person who submitted an event. Never stored.
_PRIVATE_FIELDS = ("submittedById", "submittedByAccountId", "accessCode", "@search.score", "recScore")


def event_url(event_id: Any) -> str:
    return f"{BASE}/event/{event_id}"


def scrub(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in _PRIVATE_FIELDS}


def search_events(http: HttpClient, ends_after_iso: str, starts_before_iso: str, extra_params: dict | None = None,
                  page_size: int = 100, max_pages: int = 40) -> list[dict[str, Any]]:
    """Page through upcoming approved events. Only events ending after now are requested, so historical
    events are never re-downloaded."""
    records: list[dict[str, Any]] = []
    for page in range(max_pages):
        params = {
            "endsAfter": ends_after_iso,
            "startsBefore": starts_before_iso,
            "orderByField": "endsOn",
            "orderByDirection": "ascending",
            "status": "Approved",
            "take": page_size,
            "skip": page * page_size,
            **(extra_params or {}),
        }
        data = http.get_json(SEARCH_URL, params=params, headers={"Accept": "application/json"})
        batch = data.get("value") or []
        records.extend(batch)
        total = data.get("@odata.count") or 0
        if not batch or len(records) >= total:
            break
    return records


def fetch_detail(http: HttpClient, event_id: Any, expire_after: int | None = None) -> dict[str, Any] | None:
    try:
        return scrub(http.get_json(DETAIL_URL.format(id=event_id), headers={"Accept": "application/json"},
                                   expire_after=expire_after))
    except Exception as exc:  # a single missing event must not break the source
        log.warning("terplink detail %s failed: %s", event_id, exc)
        return None


def to_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def event_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Map a TerpLink search record *or* detail record onto Event fields."""
    address = data.get("address") if isinstance(data.get("address"), dict) else {}
    location = (data.get("location") or address.get("name") or "").strip() or None
    online = address.get("onlineLocation")
    categories = list(data.get("categoryNames") or [c.get("name") for c in data.get("categories") or [] if c.get("name")])
    theme = data.get("theme") if data.get("theme") not in (None, "", "Unknown") else None
    benefits = list(data.get("benefitNames") or data.get("benefits") or [])
    image = data.get("imageUrl") or (IMAGE_URL.format(path=data["imagePath"]) if data.get("imagePath") else None)
    street = ", ".join(filter(None, [address.get("line1"), address.get("city"), address.get("state")]))
    description = html_to_text(data.get("description"))
    is_online = bool(online) or bool(location and ONLINE_PATTERN.search(location))

    fields: dict[str, Any] = {
        "source_event_id": str(data["id"]),
        "source_url": event_url(data["id"]),
        "title": data["name"],
        "description": description,
        "summary": summarize(description),
        "start_time": parse_datetime(data["startsOn"]),
        "end_time": parse_datetime(data.get("endsOn")),
        "venue_name": location,
        "address": street or None,
        "latitude": to_float(data.get("latitude") or address.get("latitude")),
        "longitude": to_float(data.get("longitude") or address.get("longitude")),
        "organizer_name": (data.get("organizationName") or "").strip() or None,
        "image_url": image,
        "registration_url": event_url(data["id"]),
        "is_umd": True,
        "is_online": is_online,
        "source_categories": categories + benefits,
        "external_refs": {"terplink": str(data["id"])},
        "extra": {
            "organization_id": data.get("organizationId"),
            "student_organization": data.get("branchId") == STUDENT_ORG_BRANCH_ID if data.get("branchId") else None,
            "rsvp_total": data.get("rsvpTotal"),
            "benefits": benefits,
            # One coarse label per event; the tagger only falls back to it.
            "theme": theme,
        },
    }
    if "Free Food" in benefits:
        fields["extra"]["free_food"] = True
    return fields


def is_public(data: dict[str, Any]) -> bool:
    status = data.get("status") or (data.get("state") or {}).get("status")
    return data.get("visibility", "Public") == "Public" and status in (None, "Approved")


@register
class TerpLinkCollector(BaseCollector):
    source_name = "terplink"
    display_name = "TerpLink"
    scraper_version = "1"

    def fetch(self) -> list[RawEvent]:
        records = search_events(self.http, self.now.isoformat(), self.window_end.isoformat())
        return [self.raw(r["id"], scrub(r), event_url(r["id"])) for r in records]

    def parse(self, raw: RawEvent) -> list[Event]:
        if not is_public(raw.raw_data):
            return []
        return [self.event(**event_fields(raw.raw_data))]
