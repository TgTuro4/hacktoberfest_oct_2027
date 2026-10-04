# TerpLink

A Next.js campus discovery app for events and groups, with Snowflake persistence and Cortex Search recommendations. Built around the team's LIFEDATA schema. Login and people matching are outside this delivery's scope.

## Start locally

Use Node.js 22 or newer:

```sh
npm ci
npm run dev
```

Open http://localhost:3000. With no environment configuration, demo mode uses fictional cards and browser storage. Nothing silently pretends to be an AI result.

## Connect Snowflake

Read **[START_HERE.md](./START_HERE.md)** for the exact migration and environment setup. If you already ran SQL files 01–05, run only `sql/06_live_backend.sql` next. It extends the existing tables; it does not replace them or reset the earlier prototype.

There are two independent server tokens:

- `SNOWFLAKE_SEARCH_TOKEN`: role-restricted catalog search token (`TERPLINK_SEARCH_APP`).
- `SNOWFLAKE_APP_TOKEN`: role-restricted database token (`TERPLINK_DATA_APP`) for profile saves, publishing and swipes. The existing search token cannot perform these writes.

Both stay in `.env.local`, never GitHub or frontend JavaScript. Copy `.env.example` to get all settings. Live persistence is explicitly enabled with `SNOWFLAKE_BACKEND_ENABLED=true`; when enabled, configuration/database failures show an error rather than falling back to local saves.

## Features

- Shared campus catalog with events/groups filters, swipe gestures and saved cards.
- Create publishes reviewed cards and normalized tags to Snowflake in a transaction. Retry keys reduce duplicate publishing; unsuccessful writes never claim success.
- Major, bio, interest tags and availability are saved to a private guest profile in live mode.
- Interested/pass decisions persist through reloads and exclude cards from discovery.
- Cortex Search ranks the catalog using major, bio and interests. Live mode loads the stored profile and history server-side, then rechecks search results against current records to remove stale cancellations and swiped cards.
- Refresh catalog retrieves other teammates' published cards. New cards appear immediately in the regular catalog; the search index refreshes separately (target lag: five minutes).
- Reset in live mode clears only the current guest's profile/decisions. Published shared cards stay available.
- AI announcement extraction remains available through the existing `/api/prefill` integration; it requires its own original credentials. Exact sample prefill stays explicitly labeled as a prewritten demo.
- Flyer preview stays local. Image extraction/upload is not implemented.

Guest identity uses a signed, HTTP-only cookie lasting 30 days. It is not account login: another browser gets another profile, and deleting the cookie or changing SESSION_SECRET loses access to the old guest profile. No user password is read or written. Database access to user identity uses a limited view excluding the supplied password column.

Availability is saved free text, not a scheduling filter. Interested means a bookmark, not event registration or group membership.

## API map

| Endpoint | Purpose |
| --- | --- |
| `GET /api/state` | Initialize/load the current guest's workspace or announce local mode |
| `POST /api/profile` | Save the current guest's profile and normalized interest tags |
| `POST /api/items` | Publish an event/group with an idempotency key |
| `POST /api/swipes` | Save interested/pass for a catalog ID |
| `POST /api/reset` | Reset this guest's profile and decisions |
| `POST /api/recommendations` | Profile-based Cortex Search with eligibility rechecks |
| `POST /api/prefill` | Existing announcement extraction |

User identity is taken from the signed cookie, never a user ID supplied by the client. Inputs are bounded/validated and SQL values are bound. Database mutations require same-origin requests. Driver errors, SQL and credentials are not returned to browsers.

## Verify

```sh
npm run typecheck
npm test
npm run build
npx playwright install chromium webkit
npm run test:e2e
```

See [VERIFICATION.md](./VERIFICATION.md) for actual results and limits. Live Snowflake migration/driver permissions must be tested in your account; this workspace has no private tokens.

## Deployment limits

This is a one-server hackathon application. Guest operations are serialized per guest in that server, because standard Snowflake tables do not enforce UNIQUE/foreign-key constraints. Before using multiple server instances or serving a public audience, add an authenticated account system, distributed consistency/rate limiting and database constraint enforcement appropriate to that deployment. Listing fetches are capped at 1,000 cards; this prototype has no catalog pagination. The search filter sends up to 500 recent swipe IDs and rechecks all history against the source, so heavily swiped catalogs may return fewer recommendations.

Use HTTPS and `COOKIE_SECURE=true` when deploying. Do not deploy as a static export; the API routes require the Next.js server. Server-side tokens must have network-policy access from the actual server computer.
