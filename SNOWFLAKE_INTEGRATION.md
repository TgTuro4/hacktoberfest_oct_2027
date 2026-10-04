# Snowflake integration

The integrated project now supports server-side guest profiles, catalog publishing and persistent swipes in addition to AI discovery. Start with [START_HERE.md](./START_HERE.md); the older search-only handoff has been superseded.

## Data mapping

- USERS.APP_USER_KEY maps an opaque signed browser session to a user ID. USER_IDENTITIES exposes only USER_ID/APP_USER_KEY to the app role; the password column is untouched.
- PROFILES stores name, major, bio and availability. PROFILE_TAGS/TAGS store interests.
- GROUPS/GROUP_TAGS and EVENTS/EVENT_TAGS are the shared catalog. Added descriptive/location/time/demo fields support the existing CampusItem cards.
- APP_ITEM_KEY identifies a publish attempt; CREATED_BY_USER_ID records its guest owner.
- SWIPES stores interested/pass decisions with the session-derived USER_ID and a typed `event:<id>` or `group:<id>` key.
- DISCOVERY_CATALOG joins normalized descriptions/tags. TERPLINK_SEARCH indexes it using full refresh for this small demo catalog.

Code uses stable card IDs `snowflake:event:<id>` and `snowflake:group:<id>`. Event timestamps are interpreted and displayed in America/New_York. Profiles and publishing run transactions, including their tag relationship updates. Reset is a transaction and never deletes shared catalog items. Guest mutations are serialized within the single app server; standard Snowflake constraints do not guarantee cross-server uniqueness.

The search role remains read-only. The separate data role grants only the reads/inserts/updates/deletes needed by the routes. Neither client JavaScript nor SQL scripts contain credentials. A token is a server credential, not an app user's login.

The website's demo mode remains separate from live mode. Browser-created demo records are not silently migrated into the shared database. In live mode, the stored profile/history overrides client-supplied recommendations data, and candidates are rechecked against live rows before returning results.

Official references: [Cortex Search API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/query-cortex-search-service), [PATs](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens), [Node driver execution](https://docs.snowflake.com/en/developer-guide/node-js/nodejs-driver-execute), [Snowflake transactions](https://docs.snowflake.com/en/sql-reference/transactions).
