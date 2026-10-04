# UMD Event Ingestion

Collects events happening on and around the University of Maryland, College Park from 11 sources, normalizes
them into one event model, merges duplicate listings, tags them, and writes load-ready files for Snowflake.
A small API serves the same data to the frontend.

```
collectors ─► RAW_EVENTS ─► normalize + tag ─► dedupe ─► geocode ─► EVENTS / EVENT_SOURCES / VENUES ─► exports ─► Snowflake
```

## Quick start

```bash
cd event-ingestion
uv sync                      # Python 3.11+; installs into .venv
uv run umd-events ingest     # scrape every source, build events, write data/exports/
uv run umd-events stats      # what was collected
uv run umd-events serve      # API on http://127.0.0.1:8000  (docs at /docs)
uv run pytest                # offline tests against saved fixtures
```

The first run takes a few minutes (it fills the HTTP cache). Re-runs within 30 minutes are served from the
cache; run hourly at most. Copy `.env.example` to `.env` to change settings.

## Sources

| Source | How it is collected | Notes |
|---|---|---|
| `umd_calendar` | Public GraphQL API behind calendar.umd.edu/search + event pages | Event pages render slowly when uncached, so venues are filled in progressively (150 new pages per run, in-person events in the next 60 days) |
| `terplink` | TerpLink (Campus Labs Engage) public JSON search API | Only events ending after now are requested |
| `see` | SEE's TerpLink org events + best-effort parse of see.umd.edu event pages | Wix pages with no parseable date are skipped |
| `terps_after_dark` | terpsafterdark.umd.edu cards + TerpLink "Terps After Dark" category | Cards link TerpLink IDs, which give exact merges |
| `umd_athletics` | umterps.com SIDEARM calendar JSON | Home games / College Park only |
| `clarice` | Month calendar + each event page (one event per performance) | Prices parsed, booking fees ignored |
| `college_park` | CivicPlus iCalendar feeds (City Events, CPAE arts, seniors, markets) | Council/board meetings and private room bookings filtered out |
| `hyattsville` | CivicPlus iCalendar feeds | |
| `pg_parks` | pgparks.com The Events Calendar REST API | Only facilities near campus (Aviation Museum, Riversdale, Bladensburg Waterfront, Brentwood Arts Exchange, Langley Park) |
| `recwell` | Intramural sports calendar table | Emits registration_open / registration_deadline / activity events |
| `ticketmaster` | Discovery API v2, 10 miles around campus | Needs a free `TICKETMASTER_API_KEY`; skipped otherwise |

Adding a source: write `src/umd_events/collectors/<name>.py` with a `BaseCollector` subclass decorated with
`@register`, and add one import line in `collectors/__init__.py`. Nothing downstream changes.

## Outputs

`data/exports/` (rewritten by every `ingest` or `export`):

| File | Use |
|---|---|
| `EVENTS.jsonl` / `.parquet` / `.csv` | Deduplicated events (the main table) |
| `EVENT_SOURCES.*` | Which source listings were merged into each event |
| `RAW_EVENTS.*` | Every distinct version of every source record, as collected |
| `VENUES.*` | Known venues + all UMD buildings with coordinates |
| `INGESTION_RUNS.*` | Per-source run log (status, counts, errors) |
| `EVENT_EMBEDDINGS.*` | Optional vectors (`umd-events embed`) |
| `frontend_events.json` | Upcoming events in the swipe-UI shape |

`.jsonl` is what the Snowflake loader uses. `data/events.duckdb` is the local store (same tables) that keeps
state between runs. Delete `data/` to start over.

## Loading into Snowflake

Full handoff (every column, relationships, load options, verification): [SNOWFLAKE_HANDOFF.md](SNOWFLAKE_HANDOFF.md).

Table definitions live in `src/umd_events/storage/schema.py`; `sql/snowflake_schema.sql` and
`sql/snowflake_load.sql` are generated from it (`umd-events snowflake-sql`).

**Option A: from this machine (recommended)**

```bash
uv sync --extra snowflake
# fill the SNOWFLAKE_* values in .env (account, user, password or key file, warehouse, database, schema)
uv run umd-events load-snowflake
```

It creates the schema, tables and views if missing, PUTs each `.jsonl` to an internal stage, COPYs it into a
temp table and MERGEs on the table key. Loading twice is safe. Future events no longer in the export are
deleted.

**Option B: by hand in Snowsight**

1. Run `sql/snowflake_schema.sql` in a worksheet.
2. Create the stage (first statement of `sql/snowflake_load.sql`), then upload each
   `data/exports/<TABLE>.jsonl` into `@UMD_EVENTS_STAGE/<TABLE>/`.
3. Run the rest of `sql/snowflake_load.sql`.

Views created: `UPCOMING_EVENTS`, `FREE_UPCOMING_EVENTS`, `FRONTEND_EVENTS` (frontend field names).

## API

`umd-events serve` reads the local store.

- `GET /events?categories=movie,comedy&radius_miles=2&free_only=true&include_meetings=false&q=bingo&limit=50`
  (multi-week umbrella listings are hidden unless `include_ongoing=true`)
- `GET /events/{id}`: full description, extra fields and every source listing
- `GET /tags`, `GET /sources`, `GET /health`

From Python: `from umd_events.query import get_upcoming_events`.

## Tagging

Rules always run. Each event gets tags from the brief's taxonomy, based on source categories (TerpLink themes,
calendar topics, PG Parks categories), keywords in the title/summary, and per-source defaults.

Optional local LLM (free, open source, runs on your machine):

```bash
# install Ollama from https://ollama.com, then:
ollama pull qwen2.5:3b
uv run umd-events ingest --llm-tags
```

LLM tags are added to the rule tags and cached by content hash, so only new or changed events are sent to
the model. Events with the fewest rule tags go first, capped at `LLM_MAX_EVENTS_PER_RUN`. On a laptop CPU
expect a few seconds per event.

## Commands

| Command | |
|---|---|
| `umd-events ingest [--source X] [--llm-tags] [--reprocess] [--no-export]` | Run the pipeline. `--reprocess` re-parses stored raw payloads without scraping |
| `umd-events export` | Rewrite `data/exports/` from the local store |
| `umd-events stats` | Counts, completeness, top tags |
| `umd-events sources` | List registered sources |
| `umd-events serve` | Start the API |
| `umd-events embed` | Add bge-small embeddings (`uv sync --extra embeddings`) |
| `umd-events snowflake-sql` | Regenerate `sql/` |
| `umd-events load-snowflake` | Load exports into Snowflake |

## Being a good citizen

Descriptive User-Agent, an on-disk HTTP cache, a 0.5 s minimum gap between uncached requests to a host,
retries with exponential backoff (honoring `Retry-After`), public APIs and feeds instead of HTML wherever
they exist, no login-protected data, and submitter contact info stripped from TerpLink payloads.
