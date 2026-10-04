"""Cross-source duplicate detection and merging.

Two records are the same event when they share an external ID (e.g. a Terps After Dark card links the same
TerpLink event), or when their normalized titles are similar, their start times are close, and their venues
match:

    duplicate_score = 0.60 * title_similarity + 0.25 * time_similarity + 0.15 * venue_similarity

Within one source, only exact repeat postings merge (same title, start, organizer and place; organizers often
post an event twice). Otherwise a merged cluster never holds two records from one source.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass

from rapidfuzz import fuzz

from ..models import Event
from ..normalize.categories import valid_tags
from ..normalize.titles import normalize_title
from ..normalize.venues import normalize_venue_name

log = logging.getLogger(__name__)

# Which source's version of a field wins when records merge: specialized sources first.
SOURCE_PRIORITY = [
    "umd_athletics", "clarice", "see", "terps_after_dark", "pg_parks", "recwell", "college_park",
    "hyattsville", "terplink", "umd_calendar", "ticketmaster",
]

MERGE_THRESHOLD = 85.0
MAX_TIME_DELTA_MIN = 30
# Titles too generic to merge on alone ("Tabling" by two different clubs at noon).
_GENERIC_TITLE = re.compile(
    r"^(gbm|general body meeting|general meeting|meeting|weekly meeting|club meeting|practice|tabling|"
    r"office hours|rehearsal|info session|information session|social|workshop|open house)$"
)


def _priority(source: str) -> int:
    return SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else len(SOURCE_PRIORITY)


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    score = fuzz.ratio(a, b)
    if min(len(a.split()), len(b.split())) >= 3:
        # "fall spooky movie series" vs "fall spooky movie series coraline"
        score = max(score, 0.95 * fuzz.token_set_ratio(a, b))
    return score


def time_similarity(a: Event, b: Event) -> float:
    if a.start_time.date() != b.start_time.date():
        return 0.0
    if a.all_day or b.all_day:
        return 60.0  # same day, at least one time unknown
    delta = abs((a.start_time - b.start_time).total_seconds()) / 60
    if delta > MAX_TIME_DELTA_MIN:
        return 0.0
    return 100.0 * (1 - delta / 60)


def venue_similarity(a: Event, b: Event) -> float:
    if a.venue_id and b.venue_id:
        return 100.0 if a.venue_id == b.venue_id else 0.0
    na, nb = normalize_venue_name(a.venue_name), normalize_venue_name(b.venue_name)
    if na and nb:
        return float(fuzz.token_set_ratio(na, nb))
    return 50.0  # unknown on one side: neutral


@dataclass
class MatchResult:
    score: float
    reason: str


def _same_organizer(a: Event, b: Event, required: bool) -> bool:
    if not a.organizer_name or not b.organizer_name:
        return not required
    return normalize_title(a.organizer_name) == normalize_title(b.organizer_name)


def _distinctive(title: str) -> bool:
    return len(title) >= 12 and not _GENERIC_TITLE.match(title)


def same_source_duplicate(a: Event, b: Event, title_a: str, title_b: str) -> bool:
    """The same listing posted twice on one source: identical title and start, same organizer and place.
    Generic titles ("Tabling", "GBM") also need a known, identical organizer."""
    return (
        a.source == b.source
        and title_a == title_b
        and a.start_time == b.start_time
        and _same_organizer(a, b, required=not _distinctive(title_a))
        and venue_similarity(a, b) >= 50
    )


def match(a: Event, b: Event, title_a: str, title_b: str) -> MatchResult | None:
    if a.source == b.source:
        return None
    shared = {k: v for k, v in a.external_refs.items() if b.external_refs.get(k) == v}
    if shared:
        return MatchResult(100.0, f"external_ref:{next(iter(shared))}")
    t_time = time_similarity(a, b)
    if t_time == 0:
        return None
    # Identical, non-generic title at the identical start time: venue text often disagrees between sources
    # ("The Mall" vs "Stamp Student Union") for what is plainly one event.
    two_known_places = a.venue_id and b.venue_id and a.venue_id != b.venue_id
    if title_a == title_b and a.start_time == b.start_time and _distinctive(title_a) and not two_known_places:
        return MatchResult(98.0, "exact title+start")
    t_title = title_similarity(title_a, title_b)
    t_venue = venue_similarity(a, b)
    score = 0.60 * t_title + 0.25 * t_time + 0.15 * t_venue
    if t_title >= 90 and t_time >= 50 and t_venue >= 50:
        return MatchResult(score, "title+time+venue")
    if score >= MERGE_THRESHOLD and t_title >= 80 and t_venue >= 40:
        return MatchResult(score, "weighted")
    return None


class _UnionFind:
    def __init__(self, items: list[Event]):
        self.parent = list(range(len(items)))
        self.sources = [{e.source} for e in items]

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int, same_source_ok: bool = False) -> bool:
        ri, rj = self.find(i), self.find(j)
        if ri == rj:
            return False
        if not same_source_ok and self.sources[ri] & self.sources[rj]:
            return False  # would put two different records from one source in a cluster
        self.parent[rj] = ri
        self.sources[ri] |= self.sources[rj]
        return True


def _is_placeholder(url: str | None) -> bool:
    return not url or "placeholder" in url.lower()


def merge_cluster(members: list[Event]) -> Event:
    ordered = sorted(members, key=lambda e: (_priority(e.source), e.all_day, -len(e.description or "")))
    primary = ordered[0]
    canonical = primary.model_copy(deep=True)

    timed = next((e for e in ordered if not e.all_day), None)
    if canonical.all_day and timed:
        canonical.start_time, canonical.end_time, canonical.all_day = timed.start_time, timed.end_time, False
    for name in ("end_time", "summary", "venue_name", "venue_id", "address", "latitude", "longitude",
                 "organizer_name", "registration_url", "price_min", "price_max", "is_free", "event_type"):
        if getattr(canonical, name) is None:
            setattr(canonical, name, next((getattr(e, name) for e in ordered if getattr(e, name) is not None), None))
    if canonical.latitude is None or canonical.longitude is None:
        located = next((e for e in ordered if e.latitude is not None and e.longitude is not None), None)
        canonical.latitude, canonical.longitude = (located.latitude, located.longitude) if located else (None, None)
    descriptions = [e.description for e in ordered if e.description]
    canonical.description = max(descriptions, key=len) if descriptions else None
    canonical.image_url = next((e.image_url for e in ordered if not _is_placeholder(e.image_url)),
                               next((e.image_url for e in ordered if e.image_url), None))
    tags = {t for e in members for t in e.tags}
    if len(tags) > 1:
        tags.discard("other")
    canonical.tags = valid_tags(tags)
    canonical.is_umd = any(e.is_umd for e in members)
    canonical.is_online = all(e.is_online for e in members)
    canonical.sources = sorted({e.source for e in members}, key=_priority)
    canonical.external_refs = {k: v for e in reversed(ordered) for k, v in e.external_refs.items()}
    canonical.source_categories = sorted({c for e in members for c in e.source_categories})
    canonical.extra = {k: v for e in reversed(ordered) for k, v in e.extra.items() if v not in (None, [], {})}
    return canonical


@dataclass
class DedupeResult:
    events: list[Event]
    # (canonical_event_id, member record)
    memberships: list[tuple[str, Event]]
    merged_pairs: int


def deduplicate(records: list[Event]) -> DedupeResult:
    uf = _UnionFind(records)
    titles = [normalize_title(e.title) for e in records]
    by_day: dict[object, list[int]] = defaultdict(list)
    for i, e in enumerate(records):
        by_day[e.start_time.date()].append(i)

    # External-ID matches can span days (a card and its TerpLink event may disagree on dates).
    by_ref: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, e in enumerate(records):
        for key, value in e.external_refs.items():
            by_ref[(key, value)].append(i)

    # Pass 1: collapse repeat postings within a source, so each repeat counts as one listing below.
    merged = 0
    for indexes in by_day.values():
        for x in range(len(indexes)):
            for y in range(x + 1, len(indexes)):
                i, j = indexes[x], indexes[y]
                if same_source_duplicate(records[i], records[j], titles[i], titles[j]):
                    merged += uf.union(i, j, same_source_ok=True)

    # Pass 2: cross-source matches.
    candidates: list[tuple[float, int, int, str]] = []
    for indexes in by_ref.values():
        for x in range(len(indexes)):
            for y in range(x + 1, len(indexes)):
                i, j = indexes[x], indexes[y]
                if records[i].source != records[j].source:
                    candidates.append((101.0, i, j, "external_ref"))
    for indexes in by_day.values():
        for x in range(len(indexes)):
            for y in range(x + 1, len(indexes)):
                i, j = indexes[x], indexes[y]
                result = match(records[i], records[j], titles[i], titles[j])
                if result:
                    candidates.append((result.score, i, j, result.reason))

    for score, i, j, reason in sorted(candidates, reverse=True):  # strongest matches claim records first
        if uf.union(i, j):
            merged += 1
            log.debug("merge %.0f %s: %r [%s] + %r [%s]", score, reason, records[i].title, records[i].source,
                      records[j].title, records[j].source)

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(len(records)):
        clusters[uf.find(i)].append(i)

    events, memberships = [], []
    for indexes in clusters.values():
        members = [records[i] for i in indexes]
        canonical = merge_cluster(members) if len(members) > 1 else members[0].model_copy(deep=True)
        events.append(canonical)
        memberships.extend((canonical.event_id, m) for m in members)
    events.sort(key=lambda e: e.start_time)
    log.info("dedupe: %d source records -> %d events (%d merges)", len(records), len(events), merged)
    return DedupeResult(events, memberships, merged)
