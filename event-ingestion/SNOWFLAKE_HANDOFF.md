# UMD Events: Snowflake Handoff

**Task for whoever picks this up:** load the UMD event data into Snowflake and confirm the frontend view
(`FRONTEND_EVENTS`) returns rows. Everything you need is in this document and the files next to it. The load
procedure has not been run against a real Snowflake account yet, so read [Known gaps](#known-gaps) and
report any SQL errors verbatim.

---

## 1. What this is

An event-discovery app ("swipe through things to do") for the University of Maryland, College Park needs
one table of upcoming events. A Python pipeline (`event-ingestion/` in the repo
`github.com/TgTuro4/hacktoberfest_oct_2027`, branch `webscraping`) collects events from 10 public sources,
normalizes them into one schema, merges duplicates that appear on several sources, tags them with a fixed
category list, and exports one file per Snowflake table.

| Source key | Source | Collected via |
|---|---|---|
| `umd_calendar` | calendar.umd.edu | the site's public GraphQL API + event pages |
| `terplink` | terplink.umd.edu (student orgs) | public JSON search API |
| `see` | Student Entertainment Events | SEE's TerpLink org + see.umd.edu pages |
| `terps_after_dark` | terpsafterdark.umd.edu | site cards + TerpLink category |
| `umd_athletics` | umterps.com (home games only) | SIDEARM calendar JSON |
| `clarice` | theclarice.umd.edu | calendar + event pages (one event per performance) |
| `college_park` | City of College Park | iCalendar feeds |
| `hyattsville` | City of Hyattsville | iCalendar feeds |
| `pg_parks` | PG County Parks, facilities near campus | The Events Calendar REST API |
| `recwell` | UMD RecWell intramurals | intramural calendar table |
| `ticketmaster` | Ticketmaster (not in this snapshot; needs an API key) | Discovery API |

**Snapshot of 2026-10-04:** 1,912 source listings merged into **1,695 events** (151 of them found on 2+
sources). Events run through 2027-01-02. Some started earlier but are still running (multi-week exhibits).

---

## 2. Files

In the bundle zip (`umd_events_snowflake_bundle.zip`):

```
SNOWFLAKE_HANDOFF.md        this file
data/EVENTS.jsonl           1,695 rows   main table: deduplicated events
data/EVENT_SOURCES.jsonl    1,912 rows   which source listing(s) were merged into each event
data/VENUES.jsonl             437 rows   known venues + all UMD buildings, with coordinates
data/INGESTION_RUNS.jsonl      54 rows   per-source scrape log
data/RAW_EVENTS.jsonl       2,382 rows   original source payloads, one row per distinct version (optional)
sql/snowflake_schema.sql    CREATE TABLE / CREATE VIEW statements
sql/snowflake_load.sql      stage + COPY + MERGE statements for every table
```

In the repo, the same files are `event-ingestion/data/exports/<TABLE>.jsonl` (created by
`uv run umd-events ingest`; not committed) and `event-ingestion/sql/*.sql` (committed). The table definitions
come from `event-ingestion/src/umd_events/storage/schema.py`, and the SQL files are generated from it with
`uv run umd-events snowflake-sql`. Change the schema there, not in the SQL.

`EVENT_EMBEDDINGS` exists in the schema but is empty in this snapshot. Its load step just loads 0 rows.

**Privacy:** the data is public event listings, but some organizers put personal emails and phone numbers in
their descriptions. Don't commit the data files to the public repo or post them publicly.

---

## 3. Data format

- **JSON Lines**, UTF-8: one JSON object per line, one file per table, keys exactly equal to column names
  (lowercase).
- **Timestamps:** ISO 8601 strings with a UTC offset, in America/New_York local time, e.g.
  `2026-10-05T18:00:00-04:00`. Load as `TIMESTAMP_TZ`.
- **Arrays** (`tags`, `sources`, `aliases`) are JSON arrays of strings and load as `ARRAY`.
- **Objects** (`extra`, `raw_data`) are JSON objects and load as `VARIANT`.
- Missing values are JSON `null`. `null` means **unknown**, never false or zero (for example `is_free: null`
  does not mean the event costs money).

### EVENTS (key: `event_id`)

| Column | Type | Meaning |
|---|---|---|
| event_id | STRING | 32-hex ID of the merged event. It is the ID of its primary listing, so it stays stable as long as that listing exists |
| title | STRING | display title, from the primary source |
| short_description | STRING | about 1–2 sentences, for cards |
| description | STRING | plain text (HTML stripped). The longest description among merged listings |
| start_time | TIMESTAMP_TZ | start, Eastern time |
| end_time | TIMESTAMP_TZ | null when the source gives no end |
| all_day | BOOLEAN | true when the time is unknown or all-day. start_time is then local midnight |
| venue_id | STRING | FK → VENUES.venue_id, at building/place level (e.g. `stamp-student-union`). Null if not recognized |
| venue_name | STRING | venue as the source wrote it, often a room (e.g. `Baltimore Room`) |
| address | STRING | street address when known |
| latitude, longitude | FLOAT | from the venue table or geocoding. Null for about 18% of events |
| distance_miles | FLOAT | straight-line miles from McKeldin Mall (38.98599, -76.94227) |
| organizer_name | STRING | host org/department |
| source | STRING | primary source key (section 1) |
| source_event_id | STRING | the primary listing's ID on that source |
| source_url | STRING | link to the primary listing |
| sources | ARRAY | every source the event was found on, primary first |
| image_url | STRING | |
| registration_url | STRING | tickets/RSVP/registration link |
| price_min, price_max | FLOAT | USD, when the source lists prices |
| is_free | BOOLEAN | true / false / null (unknown, which is most events) |
| price_display | STRING | `Free`, `$20–$50`, `Free–$10`, or null |
| is_umd | BOOLEAN | UMD-affiliated or at a UMD venue |
| is_online | BOOLEAN | online-only |
| event_type | STRING | one of: `activity`, `sports_game`, `performance`, `screening`, `meeting` (club GBMs/practices), `class`, `exhibit`, `ongoing` (multi-week umbrella listing), `registration_open`, `registration_deadline` |
| tags | ARRAY | zero or more of: sports, movie, concert, music, comedy, theater, dance, arts, gaming, hackathon, technology, career, academic, research, workshop, social, cultural, food, outdoors, fitness, intramural, volunteering, community, nightlife, student_organization, lecture, festival, other (`other` only when nothing else applies) |
| extra | VARIANT | source-specific fields (below) plus `external_refs` (IDs on other platforms) and `source_categories` (the source's raw labels) |
| content_hash | STRING | changes whenever the event's content changes |
| created_at | TIMESTAMP_TZ | first time the pipeline produced this event |
| updated_at | TIMESTAMP_TZ | last time its content changed |
| last_seen_at | TIMESTAMP_TZ | last pipeline run that included it |

Useful `extra` keys: athletics: `sport`, `opponent`, `home_team`, `away_team`, `home_away`,
`conference_game`, `ticket_url`, `watch_url`, `result_if_completed`. TerpLink: `organization_id`,
`student_organization`, `rsvp_total`, `benefits`, `free_food`, `theme`. UMD calendar: `audiences`,
`host_departments`, `event_topics`, `location_type`. Clarice: `presenter`, `price_text`. PG Parks:
`age_range`, `price_text`. RecWell: `sport`. Query as `extra:sport::STRING`.

### EVENT_SOURCES (key: `source`, `source_event_id`)

| Column | Type | Meaning |
|---|---|---|
| canonical_event_id | STRING | FK → EVENTS.event_id |
| source | STRING | source key |
| source_event_id | STRING | the listing's ID on that source |
| source_url | STRING | link to that listing |
| source_record_id | STRING | the pipeline's per-listing ID (equals event_id for the primary listing) |
| discovered_at | TIMESTAMP_TZ | first seen |
| last_seen_at | TIMESTAMP_TZ | last seen |

### VENUES (key: `venue_id`)

`venue_id` STRING, `canonical_name` STRING, `address` STRING, `latitude` FLOAT, `longitude` FLOAT,
`aliases` ARRAY (lowercase names that resolve to this venue), `is_umd` BOOLEAN.

### INGESTION_RUNS (key: `run_id`, `source`)

`run_id` STRING (one per pipeline run), `source` STRING, `started_at` / `completed_at` TIMESTAMP_TZ,
`status` STRING (`success` | `failed` | `skipped`), `events_found` / `events_inserted` / `events_updated` /
`events_rejected` INTEGER, `error_message` STRING.

### RAW_EVENTS (key: `ingestion_id`)

`ingestion_id` STRING, `source` STRING, `source_event_id` STRING, `source_url` STRING, `raw_data` VARIANT
(the payload exactly as collected), `scraped_at` TIMESTAMP_TZ, `scraper_version` STRING, `content_hash`
STRING. A new row is written only when a record's content changes, so the table is a version history.
Latest version: `QUALIFY ROW_NUMBER() OVER (PARTITION BY source, source_event_id ORDER BY scraped_at DESC) = 1`.

### EVENT_EMBEDDINGS (key: `event_id`), empty for now

`event_id` STRING, `model` STRING, `embedding` VECTOR(FLOAT, 384), `content_hash` STRING,
`created_at` TIMESTAMP_TZ.

### Relationships

- `EVENTS.event_id` 1 → N `EVENT_SOURCES.canonical_event_id`
- `EVENTS.venue_id` → `VENUES.venue_id` (nullable)
- `EVENT_SOURCES (source, source_event_id)` → `RAW_EVENTS (source, source_event_id)`. Exceptions: one Clarice
  raw record produces one event per performance (`<slug>:<YYYYMMDDTHHMM>`), and one RecWell raw record produces
  up to three (`<sport>:<event_type>`). For those, match the raw ID as the prefix before `:`.

### Views (created by `snowflake_schema.sql`)

- `UPCOMING_EVENTS`: events whose end (or start) is in the future
- `FREE_UPCOMING_EVENTS`: upcoming and `is_free = TRUE`
- `FRONTEND_EVENTS`: upcoming events with frontend field names: `id, title, image_url, short_description,
  start_time, end_time, all_day, distance_miles, venue, address, latitude, longitude, tags, price, is_free,
  registration_url, source, sources, source_url, event_type, is_umd, is_online`

---

## 4. Loading

### Prerequisites

- A warehouse (e.g. `COMPUTE_WH`), a database (e.g. `UMD_EVENTS`) and a schema (e.g. `PUBLIC`).
- A role with USAGE on the warehouse and database, CREATE SCHEMA on the database (only if the schema must be
  created), and CREATE TABLE, CREATE VIEW and CREATE STAGE on the schema.
- Run everything in **one session** with that database and schema selected: the load script uses temporary
  tables.

### Option A: repo CLI (does everything, including upload)

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
cd event-ingestion
uv sync --extra snowflake
cp .env.example .env
```

Fill in `.env`: `SNOWFLAKE_ACCOUNT` (account identifier, `ORGNAME-ACCOUNTNAME`), `SNOWFLAKE_USER`, and
either `SNOWFLAKE_PASSWORD` or `SNOWFLAKE_PRIVATE_KEY_FILE` (or leave both empty for browser SSO), plus
`SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`.

Put the bundle's `data/*.jsonl` files in `event-ingestion/data/exports/`, or scrape fresh data with
`uv run umd-events ingest` (about 5 minutes the first time). Then:

```bash
uv run umd-events load-snowflake
```

It creates the schema, tables, views and stage if missing, then for each table: clears the table's stage
folder, PUTs the file, COPYs it into a temp table, and MERGEs it into the real table.

### Option B: Snowsight (browser only)

1. Worksheet → select database + schema → run all of `sql/snowflake_schema.sql`.
2. Run `CREATE STAGE IF NOT EXISTS UMD_EVENTS_STAGE FILE_FORMAT = (TYPE = JSON);`
3. Data → Databases → (db) → (schema) → Stages → `UMD_EVENTS_STAGE` → **+ Files**. Upload each file into a
   folder named after its table by typing the path: `EVENTS.jsonl` → `EVENTS/`, `EVENT_SOURCES.jsonl` →
   `EVENT_SOURCES/`, `VENUES.jsonl` → `VENUES/`, `INGESTION_RUNS.jsonl` → `INGESTION_RUNS/`,
   `RAW_EVENTS.jsonl` → `RAW_EVENTS/`.
4. Run the rest of `sql/snowflake_load.sql` in the same worksheet.

### Option C: SnowSQL / Snowflake CLI (scripted, without the repo)

With [Snowflake CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index) (`snow`) configured
for the target database and schema, from the unzipped bundle folder:

```bash
snow sql -f sql/snowflake_schema.sql
snow sql -q "CREATE STAGE IF NOT EXISTS UMD_EVENTS_STAGE FILE_FORMAT = (TYPE = JSON)"
for t in EVENTS EVENT_SOURCES VENUES INGESTION_RUNS RAW_EVENTS; do
  snow sql -q "REMOVE @UMD_EVENTS_STAGE/$t/"
  snow sql -q "PUT file://$PWD/data/$t.jsonl @UMD_EVENTS_STAGE/$t/ AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
done
snow sql -f sql/snowflake_load.sql
```

PUT needs an absolute local path (on Windows: `file://C:/path/to/bundle/data/EVENTS.jsonl`). The SnowSQL
equivalent is `snowsql -f ...` / `snowsql -q ...`.

### What the load script does, per table

```sql
CREATE OR REPLACE TEMPORARY TABLE EVENTS_STAGING LIKE EVENTS;
COPY INTO EVENTS_STAGING FROM (
    SELECT $1:event_id::STRING, ..., $1:start_time::TIMESTAMP_TZ, ..., $1:tags::ARRAY, $1:extra, ...
    FROM @UMD_EVENTS_STAGE/EVENTS/
) FILE_FORMAT = (TYPE = JSON) ON_ERROR = ABORT_STATEMENT;
MERGE INTO EVENTS t USING (SELECT * FROM EVENTS_STAGING QUALIFY ROW_NUMBER() OVER (PARTITION BY EVENT_ID ...) = 1) s
ON t.EVENT_ID = s.EVENT_ID
WHEN MATCHED THEN UPDATE SET ... WHEN NOT MATCHED THEN INSERT ...;
```

Then it runs cleanup. Future events missing from the new upload were cancelled upstream or merged into
another event, so they are deleted, along with orphaned EVENT_SOURCES rows. The cleanup only runs when the
new EVENTS upload is non-empty.

**Re-running is safe** (MERGE on keys). To refresh, load a newer export the same way. Before re-uploading,
clear each stage folder (`REMOVE @UMD_EVENTS_STAGE/<TABLE>/`) so files from earlier loads aren't copied again.
Snowsight overwrites a file with the same name, so this matters only when file names change.

---

## 5. Verify

```sql
SELECT COUNT(*) FROM EVENTS;            -- 1,695 for the 2026-10-04 snapshot
SELECT COUNT(*) FROM EVENT_SOURCES;     -- 1,912
SELECT COUNT(*) FROM VENUES;            -- 437
SELECT COUNT(*) FROM RAW_EVENTS;        -- 2,382 (if loaded)

SELECT source, COUNT(*) FROM EVENTS GROUP BY 1 ORDER BY 2 DESC;
-- terplink 1022, umd_calendar 194, hyattsville 109, college_park 105, clarice 84, umd_athletics 68,
-- terps_after_dark 50, pg_parks 37, see 15, recwell 11

SELECT * FROM FRONTEND_EVENTS LIMIT 10;                 -- should return rows (needs events in the future)
SELECT id, title, start_time, tags FROM FRONTEND_EVENTS
WHERE ARRAY_CONTAINS('movie'::VARIANT, tags) AND distance_miles <= 1 ORDER BY start_time LIMIT 10;
SELECT MIN(start_time), MAX(start_time) FROM EVENTS;    -- 2026-08-18 … 2027-01-02 (Eastern offsets)
```

If `FRONTEND_EVENTS` is empty but `EVENTS` is not, the snapshot is older than the current date and needs a
fresh `ingest`.

---

## 6. Known gaps

- **Not yet run against real Snowflake.** The generated SQL uses standard features (internal stage, COPY with
  a transforming SELECT from JSON, `CREATE TEMPORARY TABLE ... LIKE`, MERGE with QUALIFY), but it is
  unverified. Likely failure points: privileges (stage/temp-table creation), the account identifier format,
  and `VECTOR(FLOAT, 384)` in `EVENT_EMBEDDINGS` on accounts without vector support. If that one fails, drop
  the `EVENT_EMBEDDINGS` table and its load block; nothing else depends on it.
- **Known-null fields:** prices (most sources don't publish them), coordinates (about 18%), images (about 42%).
- Ticketmaster is not in this snapshot (no API key).

---

## 7. Refreshing the data

From the repo: `cd event-ingestion && uv run umd-events ingest` (collect + rebuild + export; about 1 min with a
warm cache), then `uv run umd-events load-snowflake`. Events change slowly, so polling every 30–60 minutes
is plenty. `uv run umd-events stats` summarizes the local data. `event-ingestion/README.md` covers the whole
pipeline.
