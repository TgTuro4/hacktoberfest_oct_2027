# Match the existing Snowflake schema to TerpLink

The live database is `LIFEDATA.MAIN`. Its event columns currently include
`EVENT_ID`, `EVENT_TITLE`, `EVENT_DESCRIPTION`, and `SOURCE_ID`; its groups
currently have `GROUP_ID` and `GROUP_NAME`. The web forms need additional fields.

## Existing database

Paste `001_align_lifedata_with_terplink.sql` into a Snowsight SQL worksheet and
run it using the role that owns the affected tables. `PROJECT_DEVELOPER` can do
this only if it owns them; the current `RoleAllocation.sql` grants DML access,
which does not by itself permit adding columns.

The migration adds nullable columns and ends with inspection queries. It does
not recreate tables, delete records, change IDs, or fill missing facts. Adding
columns does not populate them for old rows. Backfill old events from verified
sources; leave missing details NULL. Dates and times represent campus-local time
in America/New_York.

| Web form | Snowflake column |
| --- | --- |
| Event title | `EVENTS.EVENT_TITLE` |
| Event description | `EVENTS.EVENT_DESCRIPTION` |
| Event location | `EVENTS.EVENT_LOCATION` |
| Event date | `EVENTS.EVENT_DATE` (`DATE`) |
| Event time | `EVENTS.EVENT_TIME` (`TIME`) |
| Group name | `GROUPS.GROUP_NAME` |
| Group description | `GROUPS.GROUP_DESCRIPTION` |
| Group location | `GROUPS.GROUP_LOCATION` |
| Recurring meeting details | `GROUPS.MEETING_DETAILS` |
| Card creation timestamp | `EVENTS.CREATED_AT` / `GROUPS.CREATED_AT` |
| Event interests | `EVENT_TAGS` joined to `TAGS` |
| Group interests | `GROUP_TAGS` joined to `TAGS` |

`LifeDataConstruction.sql` is the bootstrap for a new database. It now creates
the matching fields and uses `IF NOT EXISTS`. Existing tables are preserved;
the migration is still needed to add columns to them.

## What this does not do

These scripts prepare the database schema. They have not been executed against
your live account. The web app still stores published cards in localStorage and
uses Snowflake only for configured AI prefill. Database reads and publishing API
routes must be connected separately; executing this migration alone does not
make the frontend load Snowflake records.

There is no `.env.local` in the project at the time this guide was prepared.
Configure credentials there using `.env.example`; do not send secrets in chat.
The database connection will also need the database/schema names, a warehouse,
and a role with the appropriate table privileges.

The Desktop `umd_events_snowflake_bundle` defines a different EVENTS schema with
`TITLE`, `START_TIME`, and `VENUE_NAME`. Do not run its loading scripts directly
against these normalized tables. A separate schema or an explicit import mapping
is needed first.

Official references:
- [ALTER TABLE / ADD COLUMN IF NOT EXISTS](https://docs.snowflake.com/en/sql-reference/sql/alter-table)
- [Snowflake DATE, TIME, and TIMESTAMP types](https://docs.snowflake.com/en/sql-reference/data-types-datetime)
