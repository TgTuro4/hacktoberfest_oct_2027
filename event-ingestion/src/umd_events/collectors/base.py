from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, ClassVar

from pydantic import ValidationError

from ..config import Settings
from ..http import HttpClient
from ..models import Event, RawEvent
from ..normalize.times import now_eastern

log = logging.getLogger(__name__)

REGISTRY: dict[str, type["BaseCollector"]] = {}


def register(cls: type["BaseCollector"]) -> type["BaseCollector"]:
    if cls.source_name in REGISTRY:
        raise ValueError(f"duplicate collector for source {cls.source_name!r}")
    REGISTRY[cls.source_name] = cls
    return cls


@dataclass
class CollectorResult:
    source: str
    raw_events: list[RawEvent] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    rejected: int = 0
    out_of_window: int = 0
    warnings: dict[str, int] = field(default_factory=dict)
    duration_s: float = 0.0
    skipped_reason: str | None = None


class BaseCollector(ABC):
    """Interface every source implements.

    ``fetch`` talks to the network and returns one RawEvent per source record, holding everything ``parse``
    needs. ``parse`` is pure and turns a RawEvent into zero or more Events, which lets the pipeline
    reprocess stored RAW_EVENTS without scraping again.
    """

    source_name: ClassVar[str]
    display_name: ClassVar[str] = ""
    scraper_version: ClassVar[str] = "1"
    tier: ClassVar[int] = 1

    def __init__(self, http: HttpClient | None, settings: Settings):
        self.http = http
        self.settings = settings
        self.now = now_eastern()

    @abstractmethod
    def fetch(self) -> list[RawEvent]: ...

    @abstractmethod
    def parse(self, raw: RawEvent) -> list[Event]: ...

    def skip_reason(self) -> str | None:
        """Return a reason to skip this source (e.g. missing API key), or None to run it."""
        return None

    @property
    def window_end(self) -> datetime:
        return self.now + timedelta(days=self.settings.horizon_days)

    def in_window(self, event: Event) -> bool:
        ends = event.end_time or event.start_time
        if event.all_day and event.end_time is None:
            ends = event.start_time + timedelta(days=1)
        return ends >= self.now and event.start_time <= self.window_end

    def raw(self, source_event_id: Any, data: dict[str, Any], source_url: str | None = None) -> RawEvent:
        return RawEvent(
            source=self.source_name,
            source_event_id=str(source_event_id),
            source_url=source_url,
            raw_data=data,
            scraper_version=self.scraper_version,
        )

    def event(self, **fields: Any) -> Event:
        fields.setdefault("source", self.source_name)
        return Event(**fields)

    def parse_all(self, raws: list[RawEvent], result: CollectorResult) -> None:
        for raw in raws:
            try:
                parsed = self.parse(raw)
            except (ValidationError, ValueError, KeyError, TypeError, AttributeError) as exc:
                result.rejected += 1
                log.debug("[%s] rejected %s: %s", self.source_name, raw.source_event_id, exc)
                continue
            for event in parsed:
                if event.end_time and event.end_time < event.start_time:
                    event.end_time = None
                    _bump(result.warnings, "end_before_start")
                if not self.in_window(event):
                    result.out_of_window += 1
                    continue
                for name, value in (
                    ("missing_description", event.description),
                    ("missing_venue", event.venue_name or event.is_online),
                    ("missing_image", event.image_url),
                    ("missing_organizer", event.organizer_name),
                ):
                    if not value:
                        _bump(result.warnings, name)
                result.events.append(event)

    def run(self) -> CollectorResult:
        started = time.monotonic()
        result = CollectorResult(source=self.source_name)
        reason = self.skip_reason()
        if reason:
            result.skipped_reason = reason
            log.info("[%s] skipped: %s", self.source_name, reason)
            return result
        result.raw_events = self.fetch()
        self.parse_all(result.raw_events, result)
        result.duration_s = time.monotonic() - started
        log.info(
            "[%s] fetched=%d parsed=%d rejected=%d out_of_window=%d duration=%.1fs%s",
            self.source_name,
            len(result.raw_events),
            len(result.events),
            result.rejected,
            result.out_of_window,
            result.duration_s,
            (" warnings=" + ",".join(f"{k}:{v}" for k, v in sorted(result.warnings.items()))) if result.warnings else "",
        )
        return result


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1
