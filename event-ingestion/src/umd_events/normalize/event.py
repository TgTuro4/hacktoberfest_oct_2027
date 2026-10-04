"""Per-record normalization applied to every collector's output before storage and dedupe."""

from __future__ import annotations

import hashlib

from ..models import Event, compute_hash
from .prices import mentions_free_admission
from .text import clean_text, summarize
from .titles import clean_title, normalize_title
from .urls import clean_url
from .venues import ONLINE_PATTERN, venue_index

# Fields that make up an event's identity for change detection (not ids or bookkeeping).
_CONTENT_FIELDS = (
    "title", "summary", "description", "start_time", "end_time", "all_day", "venue_name", "address",
    "organizer_name", "image_url", "registration_url", "price_min", "price_max", "is_free", "event_type",
    "source_categories",
)


def record_id(source: str, source_event_id: str | None, title: str, start_iso: str, venue: str | None) -> str:
    """Deterministic per-source ID. Falls back to title+time+venue when the source has no ID."""
    if source_event_id:
        key = f"{source}|{source_event_id}"
    else:
        key = f"{source}|{normalize_title(title)}|{start_iso}|{(venue or '').lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def normalize_event(event: Event) -> Event:
    e = event.model_copy(deep=True)
    e.title = clean_title(e.title)
    e.description = clean_text(e.description)
    e.summary = clean_text(e.summary) or summarize(e.description)
    e.venue_name = clean_text(e.venue_name)
    e.address = clean_text(e.address)
    e.organizer_name = clean_text(e.organizer_name)
    e.source_url = clean_url(e.source_url) or e.source_url
    e.registration_url = clean_url(e.registration_url)
    e.image_url = clean_url(e.image_url)

    if e.venue_name and ONLINE_PATTERN.search(e.venue_name) and not e.address:
        e.is_online = True

    venue = venue_index().resolve(e.venue_name, e.address) if not (e.is_online and not e.address) else None
    if venue:
        e.venue_id = venue.venue_id
        if e.latitude is None or e.longitude is None:
            e.latitude, e.longitude = venue.latitude, venue.longitude
        if not e.address or e.address.lower() in ("college park, md", "college park, md 20742"):
            e.address = venue.address
        e.is_umd = e.is_umd or venue.is_umd
        if not e.venue_name:
            e.venue_name = venue.canonical_name

    if e.is_free is None and mentions_free_admission(" ".join(filter(None, [e.title, e.summary, e.description]))):
        e.is_free = True
        e.price_min = e.price_min if e.price_min is not None else 0.0
        e.price_max = e.price_max if e.price_max is not None else 0.0

    e.sources = [e.source]
    e.event_id = record_id(e.source, e.source_event_id, e.title, e.start_time.isoformat(), e.venue_name)
    e.content_hash = compute_hash({f: getattr(e, f) for f in _CONTENT_FIELDS})
    return e
