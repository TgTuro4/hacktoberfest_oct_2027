"""Small read-only HTTP API over the local event store. Run with `umd-events serve`."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .collectors import REGISTRY
from .config import UMD_CENTER, get_settings
from .normalize.categories import TAXONOMY
from .query import get_event, get_upcoming_events
from .storage.local import LocalStore

settings = get_settings()
app = FastAPI(title="UMD Events API", version="0.1.0",
              description="Events on and around the University of Maryland, College Park.")
app.add_middleware(CORSMiddleware, allow_origins=settings.api_cors_origins, allow_methods=["GET"], allow_headers=["*"])


def _csv(value: str | None) -> list[str] | None:
    return [v.strip() for v in value.split(",") if v.strip()] if value else None


@app.get("/health")
def health() -> dict:
    with LocalStore(settings.db_path, read_only=True) as store:
        count = store.query("SELECT count(*) AS n FROM EVENTS")[0]["n"]
    return {"status": "ok", "events": count}


@app.get("/events")
def list_events(
    start: datetime | None = None,
    end: datetime | None = None,
    radius_miles: float | None = Query(None, gt=0, description="Distance from lat/lon (default McKeldin Mall)"),
    lat: float | None = None,
    lon: float | None = None,
    categories: str | None = Query(None, description="Comma-separated tags, e.g. movie,sports,social"),
    free_only: bool = False,
    include_online: bool = True,
    include_meetings: bool = Query(True, description="False hides club GBMs/practices"),
    include_ongoing: bool = Query(False, description="True includes multi-week umbrella listings"),
    event_types: str | None = None,
    sources: str | None = None,
    q: str | None = Query(None, description="Search title, description, venue, organizer"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    origin = (lat, lon) if lat is not None and lon is not None else UMD_CENTER
    events = get_upcoming_events(
        start=start, end=end, radius_miles=radius_miles, categories=_csv(categories), origin=origin,
        free_only=free_only, include_online=include_online, include_meetings=include_meetings,
        include_ongoing=include_ongoing,
        event_types=_csv(event_types), sources=_csv(sources), search=q, limit=limit, offset=offset,
    )
    return {"count": len(events), "offset": offset, "events": events}


@app.get("/events/{event_id}")
def event_detail(event_id: str) -> dict:
    event = get_event(event_id)
    if not event:
        raise HTTPException(404, "event not found")
    return event


@app.get("/tags")
def tags() -> dict:
    with LocalStore(settings.db_path, read_only=True) as store:
        counts = {r["tag"]: r["n"] for r in store.query(
            "SELECT tag, count(*) AS n FROM (SELECT unnest(tags) AS tag FROM EVENTS) GROUP BY tag ORDER BY n DESC")}
    return {"taxonomy": list(TAXONOMY), "counts": counts}


@app.get("/sources")
def sources() -> dict:
    with LocalStore(settings.db_path, read_only=True) as store:
        runs = {r["source"]: r for r in store.last_runs()}
        counts = {r["s"]: r["n"] for r in store.query(
            "SELECT s, count(*) AS n FROM (SELECT unnest(sources) AS s FROM EVENTS) GROUP BY s")}
    return {"sources": [
        {"source": name, "name": cls.display_name, "tier": cls.tier, "events": counts.get(name, 0),
         "last_run": runs.get(name)}
        for name, cls in REGISTRY.items()
    ]}
