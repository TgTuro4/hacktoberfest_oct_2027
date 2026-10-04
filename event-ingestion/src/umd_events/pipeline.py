"""End-to-end ingestion:

collectors -> RAW_EVENTS -> normalize + rule tags -> SOURCE_EVENTS -> dedupe -> geocode -> (LLM tags)
-> EVENTS / EVENT_SOURCES / VENUES -> export files

Each source runs independently; one broken source never stops the others.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .collectors import REGISTRY, CollectorResult
from .config import Settings
from .dedupe.deduplicator import deduplicate
from .enrich.geocoding import Geocoder
from .enrich.tagging import OllamaTagger, infer_event_type, rule_tags
from .http import HttpClient
from .models import Event, compute_hash
from .normalize.categories import valid_tags
from .normalize.event import normalize_event
from .normalize.times import now_eastern
from .storage.export import export_all
from .storage.local import LocalStore

log = logging.getLogger(__name__)


@dataclass
class SourceReport:
    source: str
    status: str
    fetched: int = 0
    parsed: int = 0
    rejected: int = 0
    inserted: int = 0
    updated: int = 0
    raw_changed: int = 0
    duration_s: float = 0.0
    message: str | None = None


@dataclass
class PipelineReport:
    sources: list[SourceReport] = field(default_factory=list)
    source_records: int = 0
    events: int = 0
    merges: int = 0
    exports: dict[str, int] = field(default_factory=dict)


def prepare(event: Event) -> Event:
    e = normalize_event(event)
    e.event_type = infer_event_type(e)
    e.tags = rule_tags(e)
    return e


def canonical_hash(event: Event) -> str:
    return compute_hash(event.model_dump(mode="json", exclude={"content_hash", "extra"}))


def collect_source(name: str, store: LocalStore, http: HttpClient | None, settings: Settings, now: datetime,
                   run_id: str, reprocess: bool = False) -> SourceReport:
    collector = REGISTRY[name](http, settings)
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    report = SourceReport(name, "success")
    try:
        if reprocess:
            result = CollectorResult(source=name, raw_events=store.load_raw_events(name))
            collector.parse_all(result.raw_events, result)
        else:
            result = collector.run()
        if result.skipped_reason:
            report.status, report.message = "skipped", result.skipped_reason
        else:
            if not reprocess:
                report.raw_changed = store.insert_raw_events(result.raw_events)
            prepared = {e.event_id: e for e in (prepare(e) for e in result.events)}
            report.inserted, report.updated = store.upsert_source_events(list(prepared.values()), now,
                                                                         touch=not reprocess)
            report.fetched, report.parsed, report.rejected = len(result.raw_events), len(prepared), result.rejected
    except Exception as exc:  # one source failing must not stop the pipeline
        log.exception("[%s] failed", name)
        report.status, report.message = "failed", f"{type(exc).__name__}: {exc}"[:2000]
    report.duration_s = round(time.monotonic() - started, 1)
    store.record_run(
        run_id=run_id,
        source=name,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        status=report.status,
        events_found=report.fetched,
        events_inserted=report.inserted,
        events_updated=report.updated,
        events_rejected=report.rejected,
        error_message=report.message,
    )
    return report


def build_events(store: LocalStore, http: HttpClient | None, settings: Settings, now: datetime,
                 llm: bool | None = None) -> tuple[int, int, int]:
    records = store.load_active_source_events(now, settings.stale_after_days)
    result = deduplicate(records)
    events = result.events

    if http is not None:
        Geocoder(http, settings, store.geocode_get, store.geocode_put).fill(events)

    use_llm = settings.llm_tagging if llm is None else llm
    tagger = OllamaTagger(settings.ollama_host, settings.ollama_model)
    for e in events:
        e.content_hash = canonical_hash(e)
    if use_llm:
        ok, why = tagger.available()
        if ok:
            tagger.tag_many(
                events,
                cache_get=lambda h: store.tag_cache_get(h, tagger.model),
                cache_put=lambda h, tags: store.tag_cache_put(h, tagger.model, tags),
                limit=settings.llm_max_events_per_run,
            )
        else:
            log.warning("LLM tagging skipped: %s", why)
    for e in events:
        cached = store.tag_cache_get(e.content_hash, tagger.model)
        if cached:
            tags = set(e.tags) | set(cached)
            if len(tags) > 1:
                tags.discard("other")
            e.tags = valid_tags(tags)
        e.content_hash = canonical_hash(e)

    store.write_canonical(events, result.memberships, now)
    store.write_venues()
    return len(records), len(events), result.merged_pairs


def run_pipeline(settings: Settings, sources: list[str] | None = None, export: bool = True,
                 llm: bool | None = None, reprocess: bool = False) -> PipelineReport:
    unknown = set(sources or []) - set(REGISTRY)
    if unknown:
        raise ValueError(f"unknown source(s): {', '.join(sorted(unknown))}; known: {', '.join(REGISTRY)}")
    http = HttpClient(settings)
    now = now_eastern()
    run_id = uuid.uuid4().hex
    report = PipelineReport()
    with LocalStore(settings.db_path) as store:
        for name in sources or list(REGISTRY):
            report.sources.append(collect_source(name, store, http, settings, now, run_id, reprocess))
        report.source_records, report.events, report.merges = build_events(store, http, settings, now, llm)
        if export:
            report.exports = export_all(store, settings.export_dir)
    return report
