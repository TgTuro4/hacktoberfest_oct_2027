from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..normalize.times import ensure_eastern

EVENT_TYPES = (
    "activity",
    "sports_game",
    "performance",
    "screening",
    "meeting",
    "class",
    "exhibit",
    "ongoing",
    "registration_open",
    "registration_deadline",
)


class Event(BaseModel):
    """Canonical event model shared by every source.

    Collectors produce one Event per source record. After deduplication the same model holds the merged,
    user-facing event, with ``sources`` listing every source it was found on.
    """

    source: str
    source_event_id: str | None = None
    source_url: str

    title: str
    summary: str | None = None
    description: str | None = None

    start_time: datetime
    end_time: datetime | None = None
    all_day: bool = False

    venue_name: str | None = None
    venue_id: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    organizer_name: str | None = None

    image_url: str | None = None
    registration_url: str | None = None

    price_min: float | None = None
    price_max: float | None = None
    is_free: bool | None = None

    is_umd: bool = False
    is_online: bool = False

    event_type: str | None = None
    tags: list[str] = Field(default_factory=list)

    # Raw category labels from the source. They feed the tagger and are kept for debugging.
    source_categories: list[str] = Field(default_factory=list)
    # IDs of the same event on other platforms, e.g. {"terplink": "12480055"}. Used for exact dedupe.
    external_refs: dict[str, str] = Field(default_factory=dict)
    # Source-specific fields (sport, opponent, audiences, ...).
    extra: dict[str, Any] = Field(default_factory=dict)

    # Filled in by the pipeline.
    event_id: str | None = None
    content_hash: str | None = None
    sources: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _title_not_empty(cls, value: str) -> str:
        value = " ".join((value or "").split())
        if not value:
            raise ValueError("title is empty")
        return value

    @field_validator("source_url")
    @classmethod
    def _url_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("source_url is missing")
        return value.strip()

    @field_validator("start_time", "end_time")
    @classmethod
    def _tz_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_eastern(value) if value is not None else None
