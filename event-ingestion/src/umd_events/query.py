"""Read interface for the rest of the app. Callers never need to know which site an event came from."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from .config import get_settings
from .enrich.geocoding import haversine_miles
from .normalize.times import ensure_eastern, now_eastern
from .storage.local import LocalStore


def row_to_frontend(row: dict[str, Any], origin: tuple[float, float] | None = None) -> dict[str, Any]:
    distance = row.get("distance_miles")
    if origin and row.get("latitude") is not None and row.get("longitude") is not None:
        distance = round(haversine_miles(origin[0], origin[1], row["latitude"], row["longitude"]), 2)
    iso = lambda v: v.isoformat() if isinstance(v, datetime) else v  # noqa: E731
    return {
        "id": row["event_id"],
        "title": row["title"],
        "image_url": row.get("image_url"),
        "short_description": row.get("short_description"),
        "start_time": iso(row["start_time"]),
        "end_time": iso(row.get("end_time")),
        "all_day": row.get("all_day"),
        "distance_miles": distance,
        "venue": row.get("venue_name"),
        "address": row.get("address"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "tags": list(row.get("tags") or []),
        "price": row.get("price_display"),
        "is_free": row.get("is_free"),
        "registration_url": row.get("registration_url"),
        "source": row.get("source"),
        "sources": list(row.get("sources") or []),
        "source_url": row.get("source_url"),
        "event_type": row.get("event_type"),
        "organizer": row.get("organizer_name"),
        "is_umd": row.get("is_umd"),
        "is_online": row.get("is_online"),
    }


def get_upcoming_events(
    start: datetime | None = None,
    end: datetime | None = None,
    radius_miles: float | None = None,
    categories: list[str] | None = None,
    origin: tuple[float, float] | None = None,
    free_only: bool = False,
    include_online: bool = True,
    include_meetings: bool = True,
    include_ongoing: bool = False,
    event_types: list[str] | None = None,
    sources: list[str] | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
    store: LocalStore | None = None,
) -> list[dict[str, Any]]:
    """Upcoming events in the frontend shape.

    radius_miles is measured from ``origin`` (default: McKeldin Mall); events without coordinates are
    excluded when a radius is given. ``categories`` matches any of the given tags. Multi-week umbrella
    listings (event_type "ongoing", e.g. "Terps After Dark, Aug 27 - Oct 18") are left out unless
    ``include_ongoing`` is set.
    """
    start = ensure_eastern(start) if start else now_eastern()
    end = ensure_eastern(end) if end else start + timedelta(days=365)
    where = ["COALESCE(end_time, start_time) >= ?", "start_time <= ?"]
    params: list[Any] = [start, end]
    if categories:
        where.append("list_has_any(tags, ?)")
        params.append(categories)
    if free_only:
        where.append("is_free = TRUE")
    if not include_online:
        where.append("NOT is_online")
    if not include_meetings:
        where.append("COALESCE(event_type, '') <> 'meeting'")
    if not include_ongoing:
        where.append("COALESCE(event_type, '') <> 'ongoing'")
    if event_types:
        where.append("list_contains(?, event_type)")
        params.append(event_types)
    if sources:
        where.append("list_has_any(sources, ?)")
        params.append(sources)
    if search:
        where.append("(title ILIKE ? OR short_description ILIKE ? OR venue_name ILIKE ? OR organizer_name ILIKE ?)")
        params += [f"%{search}%"] * 4

    own_store = store is None
    store = store or LocalStore(get_settings().db_path, read_only=True)
    try:
        rows = store.query(f"SELECT * FROM EVENTS WHERE {' AND '.join(where)} ORDER BY start_time", params)
    finally:
        if own_store:
            store.close()

    events = [row_to_frontend(r, origin) for r in rows]
    if radius_miles is not None:
        events = [e for e in events if e["distance_miles"] is not None and e["distance_miles"] <= radius_miles]
    return events[offset: offset + limit]


def get_event(event_id: str, store: LocalStore | None = None) -> dict[str, Any] | None:
    own_store = store is None
    store = store or LocalStore(get_settings().db_path, read_only=True)
    try:
        rows = store.query("SELECT * FROM EVENTS WHERE event_id = ?", [event_id])
        if not rows:
            return None
        row = rows[0]
        sources = store.query(
            "SELECT source, source_event_id, source_url, discovered_at FROM EVENT_SOURCES WHERE canonical_event_id = ?",
            [event_id],
        )
    finally:
        if own_store:
            store.close()
    event = row_to_frontend(row)
    event["description"] = row.get("description")
    event["extra"] = json.loads(row["extra"]) if isinstance(row.get("extra"), str) else row.get("extra")
    event["listings"] = sources
    return event
