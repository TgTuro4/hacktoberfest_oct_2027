# Real UMD events

The October 4, 2026 bundle was imported into the existing LIFEDATA.LIFEDATA.EVENTS and EVENT_TAGS tables. Its separate EVENTS schema was not executed.

- 1,695 unique imported listings; 1,444 UMD-affiliated, 251 nearby non-UMD.
- 1,428 future-start UMD events at verification time. Past-start events, including ongoing exhibits, remain stored but are outside the current future-start feed.
- The app loads up to 5,000 catalog cards and shows the nearest upcoming events first.
- Official listing URLs appear on cards. All-day listings show “All day.” Full descriptions remain in Snowflake; card copy is limited to 2,000 characters.
- Demo cards are hidden from live discovery, but preserved in the database and in prior saved histories. Browser-only demo mode is unchanged.
- The imported snapshot is in data/umd-events/EVENTS.jsonl, ignored by Git. The private .env.local is also ignored. Do not commit either.

## Repeat import

From the project root:

```sh
node --env-file=.env.local scripts/import-umd-events.cjs data/umd-events/EVENTS.jsonl
```

The importer uses bound JSON batches, a transaction and stable APP_ITEM_KEY values. Rerunning the same snapshot adds no duplicate events or tag relationships. It does not update or delete existing event content; refreshed snapshots with edited existing events need a separate update migration. Do not run concurrent imports.

The existing data token suffices: this import needs no new tables or expanded role grants. Source provenance is preserved in the event description's official-listing prefix and in the local original snapshot. Supplementary venue, scrape-run and raw payload files are not required by the app and were not loaded.

The original database IDs and swipe references remain unchanged. UMD listings use CAMPUS=UMD; nearby listings use CAMPUS=NEAR_UMD and remain outside the UMD feed.

Restart npm run dev in this project folder after pulling these code changes. Refresh the catalog. Cortex Search uses its own refresh schedule; newly imported rows are not searchable until its index refresh completes.
