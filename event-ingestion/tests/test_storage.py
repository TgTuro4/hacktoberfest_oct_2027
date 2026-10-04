"""Local store round trip: upsert -> load -> dedupe -> canonical tables -> export files."""

import json
from datetime import datetime, timedelta

from umd_events.dedupe.deduplicator import deduplicate
from umd_events.models import Event, RawEvent
from umd_events.pipeline import prepare
from umd_events.query import get_upcoming_events
from umd_events.storage.export import export_all
from umd_events.storage.local import LocalStore
from umd_events.storage.schema import EXPORTED_TABLES

NOW = datetime.fromisoformat("2026-10-04T12:00:00-04:00")


def _events():
    start = NOW + timedelta(days=3)
    return [
        prepare(Event(source="see", source_event_id="1", source_url="https://see/1", title="SEE Presents: Coraline",
                      start_time=start, venue_name="Hoff Theater", is_umd=True)),
        prepare(Event(source="terplink", source_event_id="99", source_url="https://terplink/99", title="Coraline",
                      start_time=start + timedelta(minutes=10), venue_name="Stamp Student Union - Hoff Theater",
                      description="Free movie screening.")),
        prepare(Event(source="college_park", source_event_id="5", source_url="https://cp/5", title="Rave at the Grave",
                      start_time=start, venue_name="Duvall Field")),
    ]


def test_round_trip(tmp_path):
    with LocalStore(tmp_path / "events.duckdb") as store:
        raw = RawEvent(source="see", source_event_id="1", raw_data={"a": 1})
        assert store.insert_raw_events([raw]) == 1
        assert store.insert_raw_events([RawEvent(source="see", source_event_id="1", raw_data={"a": 1})]) == 0
        assert store.load_raw_events("see")[0].raw_data == {"a": 1}

        events = _events()
        assert store.upsert_source_events(events, NOW) == (3, 0)
        assert store.upsert_source_events(events, NOW + timedelta(hours=1)) == (0, 0)  # unchanged -> no updates

        active = store.load_active_source_events(NOW, stale_after_days=3)
        assert len(active) == 3 and all(e.start_time.tzinfo for e in active)

        result = deduplicate(active)
        store.write_canonical(result.events, result.memberships, NOW)
        store.write_venues()
        assert store.query("SELECT count(*) n FROM EVENTS")[0]["n"] == 2
        assert store.query("SELECT count(*) n FROM EVENT_SOURCES")[0]["n"] == 3

        movie = get_upcoming_events(start=NOW, categories=["movie"], store=store)
        assert [e["title"] for e in movie] == ["SEE Presents: Coraline"]  # SEE's listing wins
        assert movie[0]["sources"] == ["see", "terplink"]
        assert movie[0]["distance_miles"] < 0.5
        assert get_upcoming_events(start=NOW, radius_miles=0.5, store=store) == movie

        counts = export_all(store, tmp_path / "exports")
        assert counts["EVENTS"] == 2
        for table in EXPORTED_TABLES:
            assert (tmp_path / "exports" / f"{table.name}.jsonl").exists()
            assert (tmp_path / "exports" / f"{table.name}.parquet").exists()
        first = json.loads((tmp_path / "exports" / "EVENTS.jsonl").read_text(encoding="utf-8").splitlines()[0])
        assert first["start_time"].endswith("-04:00") and isinstance(first["tags"], list)
        assert isinstance(first["extra"], dict)
