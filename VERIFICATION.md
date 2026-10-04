# Verification — completed events/groups integration

Checked October 4, 2026 using Node.js 24.18.0, Next.js 16.3.8 and the project's locked dependencies.

## Passed on this delivery

- `npm run build`: production compilation, TypeScript and generation of pages/API routes.
- `npm run typecheck`: passed, including the new browser test sources.
- `npm test`: 26 unit/server tests passed. Coverage includes request validation, signed session expiry/tampering, SQL bindings, transaction rollback, guest ownership, publishing, recommendation decoding and search requests. Snowflake store tests use mocked query results.
- Three request-only Playwright checks against the production server: prefill validation/body bounds, recommendation request validation, and explicit local mode with disabled write endpoints.
- Manual in-app browser checks in local mode: Interested saves and advances the feed; the saved card survives reload; a new group publishes and appears first in Discover; profile changes survive reload.
- The published group was visually inspected in the mobile-sized browser viewport. Screenshot is supplied beside the ZIP.

## Still needs live verification

No private Snowflake credentials were available. SQL migration 06, the SDK connection, new data-role grants, real profile/swipe/publish operations and Cortex refresh integration have not been executed against the live account. Run the checks in START_HERE.md after configuring credentials. The user reported successful Cortex Search queries earlier; that does not verify the new write backend.

The complete automated browser suite has not passed for this delivery. Chromium launch was blocked by the macOS sandbox's Mach port restriction. Browser test files, including mocked live-mode persistence and failure handling, are included for execution on the teammate's computer.

No production load, multi-instance consistency or physical phone testing was performed. This implementation supports one app server with private guest profiles. Clearing its guest cookie creates a new profile.

## Repeat checks

```sh
npm ci
npm test
npm run typecheck
npm run build
npx playwright install chromium webkit
npm run test:e2e
```

Use TERPLINK_TEST_PORT to choose another HTTP test port when 3100 is occupied. Browser tests explicitly disable real Snowflake credentials and use mocked live responses where appropriate.
