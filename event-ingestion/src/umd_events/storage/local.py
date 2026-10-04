"""Local DuckDB store with the same tables as Snowflake. Keeps state between runs (raw history, first-seen
times, caches) and is what the API reads until the Snowflake database is ready."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb

from ..config import TIMEZONE
from ..enrich.geocoding import distance_from_campus
from ..models import Event, RawEvent
from ..normalize.prices import format_price
from ..normalize.venues import KNOWN_VENUES, venue_index
from .schema import TABLES, duckdb_ddl, duckdb_type


def _json(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


class LocalStore:
    def __init__(self, path: Path | str, read_only: bool = False):
        self.path = Path(path)
        self.con = duckdb.connect(str(self.path), read_only=read_only)
        self.con.execute(f"SET TimeZone = '{TIMEZONE.key}'")
        if not read_only:
            self.init_schema()

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> "LocalStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def init_schema(self) -> None:
        for table in TABLES.values():
            self.con.execute(duckdb_ddl(table))

    def _insert(self, table: str, rows: list[dict[str, Any]], replace: bool = False) -> None:
        """Bulk insert through a temporary NDJSON file (DuckDB's executemany is ~10ms per row)."""
        if not rows:
            return
        spec = TABLES[table].columns
        columns = [c for c, _ in spec]
        json_columns = {c for c, t in spec if t == "VARIANT"}

        def value(column: str, v: Any) -> Any:
            if isinstance(v, datetime):
                return v.isoformat()
            if column in json_columns and isinstance(v, str):
                return json.loads(v)
            return v

        types = "{" + ", ".join(f"'{c}': '{duckdb_type(t)}'" for c, t in spec) + "}"
        handle, tmp = tempfile.mkstemp(suffix=".ndjson", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps({c: value(c, row.get(c)) for c in columns}, default=str, ensure_ascii=False))
                    f.write("\n")
            verb = "INSERT OR REPLACE" if replace else "INSERT"
            path = Path(tmp).as_posix().replace("'", "''")
            self.con.execute(
                f"{verb} INTO {table} ({', '.join(columns)}) SELECT {', '.join(columns)} "
                f"FROM read_json('{path}', format = 'newline_delimited', columns = {types})"
            )
        finally:
            os.unlink(tmp)

    # ---- RAW_EVENTS -------------------------------------------------------------------------------------

    def insert_raw_events(self, raws: Iterable[RawEvent]) -> int:
        """Store a raw record only when its content changed since the last stored version."""
        raws = list(raws)
        if not raws:
            return 0
        latest = dict(
            ((s, i), h)
            for s, i, h in self.con.execute(
                """SELECT source, source_event_id, arg_max(content_hash, scraped_at)
                   FROM RAW_EVENTS WHERE source = ? GROUP BY ALL""",
                [raws[0].source],
            ).fetchall()
        )
        new = [r for r in raws if latest.get((r.source, r.source_event_id)) != r.content_hash]
        self._insert("RAW_EVENTS", [
            {**r.model_dump(exclude={"raw_data"}), "raw_data": _json(r.raw_data)} for r in new
        ])
        return len(new)

    def load_raw_events(self, source: str | None = None) -> list[RawEvent]:
        """Latest stored version of each source record (for reprocessing without scraping)."""
        where = "WHERE source = ?" if source else ""
        records = self.query(
            f"""SELECT ingestion_id, source, source_event_id, source_url, raw_data, scraped_at, scraper_version,
                       content_hash
                FROM RAW_EVENTS {where}
                QUALIFY row_number() OVER (PARTITION BY source, source_event_id ORDER BY scraped_at DESC) = 1""",
            [source] if source else [],
        )
        return [RawEvent(**{**r, "raw_data": json.loads(r["raw_data"])}) for r in records]

    # ---- SOURCE_EVENTS ----------------------------------------------------------------------------------

    def upsert_source_events(self, events: list[Event], seen_at: datetime, touch: bool = True) -> tuple[int, int]:
        """Upsert per-source normalized records. Returns (inserted, updated).

        ``touch=False`` (reprocessing stored raw data) only rewrites records that already exist and keeps their
        last_seen_at, so re-parsing old payloads never resurrects events a source has since removed.
        """
        if not events:
            return 0, 0
        ids = [e.event_id for e in events]
        existing = {
            row[0]: (row[1], row[2], row[3])
            for row in self.con.execute(
                "SELECT event_id, content_hash, first_seen_at, last_seen_at FROM SOURCE_EVENTS "
                "WHERE list_contains(?, event_id)",
                [ids],
            ).fetchall()
        }
        if not touch:
            events = [e for e in events if e.event_id in existing]
        inserted = updated = 0
        rows = []
        for e in events:
            prev = existing.get(e.event_id)
            if prev is None:
                inserted += 1
            elif prev[0] != e.content_hash:
                updated += 1
            rows.append({
                "event_id": e.event_id,
                "source": e.source,
                "source_event_id": e.source_event_id,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "content_hash": e.content_hash,
                "data": e.model_dump_json(),
                "first_seen_at": prev[1] if prev else seen_at,
                "last_seen_at": seen_at if touch or prev is None else prev[2],
                "updated_at": seen_at if (prev is None or prev[0] != e.content_hash) else None,
            })
        # updated_at must survive unchanged rows: fill from the stored value.
        unchanged = [r["event_id"] for r in rows if r["updated_at"] is None]
        if unchanged:
            stored = dict(self.con.execute(
                "SELECT event_id, updated_at FROM SOURCE_EVENTS WHERE list_contains(?, event_id)", [unchanged]
            ).fetchall())
            for r in rows:
                if r["updated_at"] is None:
                    r["updated_at"] = stored.get(r["event_id"], seen_at)
        self._insert("SOURCE_EVENTS", rows, replace=True)
        return inserted, updated

    def load_active_source_events(self, now: datetime, stale_after_days: int) -> list[Event]:
        """Upcoming records that their source still listed recently."""
        rows = self.con.execute(
            """SELECT data FROM SOURCE_EVENTS
               WHERE COALESCE(end_time, start_time + INTERVAL 1 DAY) >= ? AND last_seen_at >= ?""",
            [now, now - timedelta(days=stale_after_days)],
        ).fetchall()
        return [Event.model_validate_json(r[0]) for r in rows]

    # ---- EVENTS / EVENT_SOURCES / VENUES ----------------------------------------------------------------

    def write_canonical(self, events: list[Event], memberships: list[tuple[str, Event]], now: datetime) -> None:
        """Replace EVENTS with the current deduplicated set, keeping created_at for known events."""
        known = {r[0]: r[1:] for r in self.con.execute(
            "SELECT event_id, created_at, content_hash, updated_at FROM EVENTS").fetchall()}
        rows = []
        for e in events:
            created_at, previous_hash, previous_update = known.get(e.event_id, (now, None, now))
            rows.append({
                "event_id": e.event_id,
                "title": e.title,
                "short_description": e.summary,
                "description": e.description,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "all_day": e.all_day,
                "venue_id": e.venue_id,
                "venue_name": e.venue_name,
                "address": e.address,
                "latitude": e.latitude,
                "longitude": e.longitude,
                "distance_miles": distance_from_campus(e.latitude, e.longitude),
                "organizer_name": e.organizer_name,
                "source": e.source,
                "source_event_id": e.source_event_id,
                "source_url": e.source_url,
                "sources": e.sources,
                "image_url": e.image_url,
                "registration_url": e.registration_url,
                "price_min": e.price_min,
                "price_max": e.price_max,
                "is_free": e.is_free,
                "price_display": format_price(e.price_min, e.price_max, e.is_free),
                "is_umd": e.is_umd,
                "is_online": e.is_online,
                "event_type": e.event_type,
                "tags": e.tags,
                "extra": _json({**e.extra, "external_refs": e.external_refs, "source_categories": e.source_categories}),
                "content_hash": e.content_hash,
                "created_at": created_at,
                "updated_at": now if previous_hash != e.content_hash else previous_update,
                "last_seen_at": now,
            })
        self.con.execute("BEGIN")
        try:
            self.con.execute("DELETE FROM EVENTS")
            self._insert("EVENTS", rows)

            discovered = {
                (s, i): d for s, i, d in
                self.con.execute("SELECT source, source_event_id, discovered_at FROM EVENT_SOURCES").fetchall()
            }
            mapping = [{
                "canonical_event_id": canonical_id,
                "source": m.source,
                "source_event_id": m.source_event_id,
                "source_url": m.source_url,
                "source_record_id": m.event_id,
                "discovered_at": discovered.get((m.source, m.source_event_id), now),
                "last_seen_at": now,
            } for canonical_id, m in memberships]
            self._insert("EVENT_SOURCES", mapping, replace=True)
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise

    def write_venues(self) -> None:
        index = venue_index()
        venues = {v.venue_id: v for v in KNOWN_VENUES} | {
            v.venue_id: v for v in index.by_id.values() if v.venue_id not in {k.venue_id for k in KNOWN_VENUES}
        }
        self._insert("VENUES", [{
            "venue_id": v.venue_id,
            "canonical_name": v.canonical_name,
            "address": v.address,
            "latitude": v.latitude,
            "longitude": v.longitude,
            "aliases": list(v.aliases),
            "is_umd": v.is_umd,
        } for v in venues.values()], replace=True)

    # ---- INGESTION_RUNS ---------------------------------------------------------------------------------

    def record_run(self, **row: Any) -> None:
        self._insert("INGESTION_RUNS", [row], replace=True)

    def last_runs(self) -> list[dict[str, Any]]:
        cur = self.con.execute(
            """SELECT source, status, started_at, events_found, events_inserted, events_updated, events_rejected,
                      error_message
               FROM INGESTION_RUNS QUALIFY row_number() OVER (PARTITION BY source ORDER BY started_at DESC) = 1
               ORDER BY source"""
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    # ---- caches -----------------------------------------------------------------------------------------

    def tag_cache_get(self, content_hash: str, model: str) -> list[str] | None:
        row = self.con.execute("SELECT tags FROM TAG_CACHE WHERE content_hash = ? AND model = ?",
                               [content_hash, model]).fetchone()
        return list(row[0]) if row else None

    def tag_cache_put(self, content_hash: str, model: str, tags: list[str]) -> None:
        self._insert("TAG_CACHE", [{"content_hash": content_hash, "model": model, "tags": tags,
                                    "created_at": datetime.now(timezone.utc)}], replace=True)

    def geocode_get(self, query: str) -> tuple[float, float] | None | bool:
        """(lat, lon) if cached, None if cached as not-found, False if never looked up."""
        row = self.con.execute("SELECT latitude, longitude FROM GEOCODE_CACHE WHERE query = ?", [query]).fetchone()
        if row is None:
            return False
        return (row[0], row[1]) if row[0] is not None else None

    def geocode_put(self, query: str, lat: float | None, lon: float | None, display_name: str | None) -> None:
        self._insert("GEOCODE_CACHE", [{"query": query, "latitude": lat, "longitude": lon,
                                        "display_name": display_name, "created_at": datetime.now(timezone.utc)}],
                     replace=True)

    def write_embeddings(self, vectors: dict[str, list[float]], model: str, hashes: dict[str, str]) -> None:
        now = datetime.now(timezone.utc)
        self._insert("EVENT_EMBEDDINGS", [
            {"event_id": k, "model": model, "embedding": v, "content_hash": hashes.get(k), "created_at": now}
            for k, v in vectors.items()
        ], replace=True)

    def embedded_hashes(self) -> dict[str, str]:
        return dict(self.con.execute("SELECT event_id, content_hash FROM EVENT_EMBEDDINGS").fetchall())

    # ---- queries ----------------------------------------------------------------------------------------

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        cur = self.con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
