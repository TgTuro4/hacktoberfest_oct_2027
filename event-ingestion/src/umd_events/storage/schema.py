"""Single definition of every table. The DuckDB schema, the Snowflake DDL and the Snowflake load statements
are all generated from this, so the local store and Snowflake cannot drift apart."""

from __future__ import annotations

from dataclasses import dataclass

EMBEDDING_DIM = 384


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[tuple[str, str], ...]  # (column, Snowflake type)
    key: tuple[str, ...]
    exported: bool = True  # local-only tables (caches) are not exported to Snowflake
    comment: str = ""


TABLES: dict[str, Table] = {
    t.name: t
    for t in [
        Table(
            "RAW_EVENTS",
            (
                ("ingestion_id", "STRING"),
                ("source", "STRING"),
                ("source_event_id", "STRING"),
                ("source_url", "STRING"),
                ("raw_data", "VARIANT"),
                ("scraped_at", "TIMESTAMP_TZ"),
                ("scraper_version", "STRING"),
                ("content_hash", "STRING"),
            ),
            key=("ingestion_id",),
            comment="Every distinct version of every source record, exactly as collected.",
        ),
        Table(
            "EVENTS",
            (
                ("event_id", "STRING"),
                ("title", "STRING"),
                ("short_description", "STRING"),
                ("description", "STRING"),
                ("start_time", "TIMESTAMP_TZ"),
                ("end_time", "TIMESTAMP_TZ"),
                ("all_day", "BOOLEAN"),
                ("venue_id", "STRING"),
                ("venue_name", "STRING"),
                ("address", "STRING"),
                ("latitude", "FLOAT"),
                ("longitude", "FLOAT"),
                ("distance_miles", "FLOAT"),
                ("organizer_name", "STRING"),
                ("source", "STRING"),
                ("source_event_id", "STRING"),
                ("source_url", "STRING"),
                ("sources", "ARRAY"),
                ("image_url", "STRING"),
                ("registration_url", "STRING"),
                ("price_min", "FLOAT"),
                ("price_max", "FLOAT"),
                ("is_free", "BOOLEAN"),
                ("price_display", "STRING"),
                ("is_umd", "BOOLEAN"),
                ("is_online", "BOOLEAN"),
                ("event_type", "STRING"),
                ("tags", "ARRAY"),
                ("extra", "VARIANT"),
                ("content_hash", "STRING"),
                ("created_at", "TIMESTAMP_TZ"),
                ("updated_at", "TIMESTAMP_TZ"),
                ("last_seen_at", "TIMESTAMP_TZ"),
            ),
            key=("event_id",),
            comment="Deduplicated, user-facing events. distance_miles is from McKeldin Mall.",
        ),
        Table(
            "EVENT_SOURCES",
            (
                ("canonical_event_id", "STRING"),
                ("source", "STRING"),
                ("source_event_id", "STRING"),
                ("source_url", "STRING"),
                ("source_record_id", "STRING"),
                ("discovered_at", "TIMESTAMP_TZ"),
                ("last_seen_at", "TIMESTAMP_TZ"),
            ),
            key=("source", "source_event_id"),
            comment="Which source listings were merged into each canonical event.",
        ),
        Table(
            "VENUES",
            (
                ("venue_id", "STRING"),
                ("canonical_name", "STRING"),
                ("address", "STRING"),
                ("latitude", "FLOAT"),
                ("longitude", "FLOAT"),
                ("aliases", "ARRAY"),
                ("is_umd", "BOOLEAN"),
            ),
            key=("venue_id",),
        ),
        Table(
            "INGESTION_RUNS",
            (
                ("run_id", "STRING"),
                ("source", "STRING"),
                ("started_at", "TIMESTAMP_TZ"),
                ("completed_at", "TIMESTAMP_TZ"),
                ("status", "STRING"),
                ("events_found", "INTEGER"),
                ("events_inserted", "INTEGER"),
                ("events_updated", "INTEGER"),
                ("events_rejected", "INTEGER"),
                ("error_message", "STRING"),
            ),
            key=("run_id", "source"),
        ),
        Table(
            "EVENT_EMBEDDINGS",
            (
                ("event_id", "STRING"),
                ("model", "STRING"),
                ("embedding", f"VECTOR(FLOAT, {EMBEDDING_DIM})"),
                ("content_hash", "STRING"),
                ("created_at", "TIMESTAMP_TZ"),
            ),
            key=("event_id",),
            comment="Optional; filled by `umd-events embed`.",
        ),
        # Local-only working tables.
        Table(
            "SOURCE_EVENTS",
            (
                ("event_id", "STRING"),
                ("source", "STRING"),
                ("source_event_id", "STRING"),
                ("start_time", "TIMESTAMP_TZ"),
                ("end_time", "TIMESTAMP_TZ"),
                ("content_hash", "STRING"),
                ("data", "VARIANT"),
                ("first_seen_at", "TIMESTAMP_TZ"),
                ("last_seen_at", "TIMESTAMP_TZ"),
                ("updated_at", "TIMESTAMP_TZ"),
            ),
            key=("event_id",),
            exported=False,
        ),
        Table(
            "TAG_CACHE",
            (("content_hash", "STRING"), ("model", "STRING"), ("tags", "ARRAY"), ("created_at", "TIMESTAMP_TZ")),
            key=("content_hash", "model"),
            exported=False,
        ),
        Table(
            "GEOCODE_CACHE",
            (
                ("query", "STRING"),
                ("latitude", "FLOAT"),
                ("longitude", "FLOAT"),
                ("display_name", "STRING"),
                ("created_at", "TIMESTAMP_TZ"),
            ),
            key=("query",),
            exported=False,
        ),
    ]
}

EXPORTED_TABLES = [t for t in TABLES.values() if t.exported]

_DUCKDB_TYPES = {
    "STRING": "VARCHAR",
    "VARIANT": "JSON",
    "ARRAY": "VARCHAR[]",
    "TIMESTAMP_TZ": "TIMESTAMPTZ",
    "FLOAT": "DOUBLE",
    "BOOLEAN": "BOOLEAN",
    "INTEGER": "BIGINT",
}


def duckdb_type(sf_type: str) -> str:
    if sf_type.startswith("VECTOR"):
        return f"FLOAT[{EMBEDDING_DIM}]"
    return _DUCKDB_TYPES[sf_type]


def duckdb_ddl(table: Table) -> str:
    cols = ",\n  ".join(f"{name} {duckdb_type(t)}" for name, t in table.columns)
    return f"CREATE TABLE IF NOT EXISTS {table.name} (\n  {cols},\n  PRIMARY KEY ({', '.join(table.key)})\n)"


def snowflake_ddl(table: Table) -> str:
    cols = ",\n    ".join(f"{name.upper()} {t}" for name, t in table.columns)
    comment = f"\nCOMMENT = '{table.comment}'" if table.comment else ""
    return f"CREATE TABLE IF NOT EXISTS {table.name} (\n    {cols}\n){comment};"


def snowflake_select(table: Table) -> str:
    """Column list that casts a staged JSON line ($1) into the table's types."""
    def expr(name: str, t: str) -> str:
        if t == "VARIANT":
            return f"$1:{name}"
        if t.startswith("VECTOR"):
            return f"$1:{name}::ARRAY::{t}"
        return f"$1:{name}::{t}"

    return ",\n        ".join(f"{expr(name, t)} AS {name.upper()}" for name, t in table.columns)


VIEWS_SQL = """
CREATE OR REPLACE VIEW UPCOMING_EVENTS AS
SELECT *
FROM EVENTS
WHERE COALESCE(end_time, start_time) >= CURRENT_TIMESTAMP()
ORDER BY start_time;

CREATE OR REPLACE VIEW FREE_UPCOMING_EVENTS AS
SELECT *
FROM UPCOMING_EVENTS
WHERE is_free = TRUE;

-- The shape the swipe/browse frontend reads.
CREATE OR REPLACE VIEW FRONTEND_EVENTS AS
SELECT
    event_id AS id,
    title,
    image_url,
    short_description,
    start_time,
    end_time,
    all_day,
    distance_miles,
    venue_name AS venue,
    address,
    latitude,
    longitude,
    tags,
    price_display AS price,
    is_free,
    registration_url,
    source,
    sources,
    source_url,
    event_type,
    is_umd,
    is_online
FROM UPCOMING_EVENTS;
""".strip()


def full_snowflake_ddl() -> str:
    parts = ["-- Generated from src/umd_events/storage/schema.py. Do not edit by hand.", ""]
    parts += [snowflake_ddl(t) + "\n" for t in EXPORTED_TABLES]
    parts.append(VIEWS_SQL)
    return "\n".join(parts) + "\n"
