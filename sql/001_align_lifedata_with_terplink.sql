-- Run in Snowsight using the role that OWNS the EVENTS and GROUPS tables.
-- SELECT/INSERT/UPDATE/DELETE grants alone do not permit these ALTER statements.
-- Targets the live normalized schema shared in this conversation, NOT the
-- incompatible scraped-event bundle schema (TITLE, START_TIME, VENUE_NAME).
-- Existing rows, IDs, source relationships, and tag relationships are preserved.
-- No dates, times, locations, descriptions, or creation dates are invented.
-- Each added column is nullable. Rerunning skips columns that already exist.

ALTER TABLE LIFEDATA.MAIN.EVENTS
    ADD COLUMN IF NOT EXISTS EVENT_LOCATION VARCHAR;
ALTER TABLE LIFEDATA.MAIN.EVENTS
    ADD COLUMN IF NOT EXISTS EVENT_DATE DATE;
ALTER TABLE LIFEDATA.MAIN.EVENTS
    ADD COLUMN IF NOT EXISTS EVENT_TIME TIME;
ALTER TABLE LIFEDATA.MAIN.EVENTS
    ADD COLUMN IF NOT EXISTS CREATED_AT TIMESTAMP_TZ;

ALTER TABLE LIFEDATA.MAIN.GROUPS
    ADD COLUMN IF NOT EXISTS GROUP_DESCRIPTION VARCHAR;
ALTER TABLE LIFEDATA.MAIN.GROUPS
    ADD COLUMN IF NOT EXISTS GROUP_LOCATION VARCHAR;
ALTER TABLE LIFEDATA.MAIN.GROUPS
    ADD COLUMN IF NOT EXISTS MEETING_DETAILS VARCHAR;
ALTER TABLE LIFEDATA.MAIN.GROUPS
    ADD COLUMN IF NOT EXISTS CREATED_AT TIMESTAMP_TZ;

-- EVENT_DATE + EVENT_TIME represent campus-local time (America/New_York).
-- Existing incomplete records remain readable, but new events published by the
-- app must provide a title, location, valid date and time. New groups require
-- a name and description. Enforce these rules in the API when publishing.

DESCRIBE TABLE LIFEDATA.MAIN.EVENTS;
DESCRIBE TABLE LIFEDATA.MAIN.GROUPS;

-- Inspect missing details before backfilling using verified source information.
-- These SELECT statements do not alter existing records.
SELECT EVENT_ID, EVENT_TITLE, EVENT_LOCATION, EVENT_DATE, EVENT_TIME
FROM LIFEDATA.MAIN.EVENTS
WHERE EVENT_LOCATION IS NULL OR EVENT_DATE IS NULL OR EVENT_TIME IS NULL
ORDER BY EVENT_ID;

SELECT GROUP_ID, GROUP_NAME, GROUP_DESCRIPTION, GROUP_LOCATION, MEETING_DETAILS
FROM LIFEDATA.MAIN.GROUPS
WHERE GROUP_DESCRIPTION IS NULL
ORDER BY GROUP_ID;
