# Finish setup on the teammate's computer

This project already includes the frontend, server routes and Snowflake integration. Work on a new Git branch, not directly on the team's main branch.

## 1. Database migration

Aayush already created LIFEDATA.LIFEDATA, sample records, TERPLINK_SEARCH and TERPLINK_SEARCH_APP. In the Snowflake website, open hackathon.sql, paste the entire contents of **sql/06_live_backend.sql**, select all and run it as ACCOUNTADMIN. It adds guest identity fields, availability, publishing keys, SWIPES and the separate TERPLINK_DATA_APP role.

If this is a new account instead, run SQL files 01 through 06 in order; file 02 is optional demo data. The scripts assume schema LIFEDATA.LIFEDATA and warehouse COMPUTE_WH. If the team uses another schema/warehouse, change every qualified reference before running.

## 2. Two private tokens

Keep the existing token restricted to TERPLINK_SEARCH_APP for AI search. Generate another token restricted to TERPLINK_DATA_APP for database writes. Do not change or expand the search token's role. Keep both tokens private.

Generate a session secret on the app computer:

```sh
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

## 3. App environment

Create **.env.local beside package.json** (not inside sql/). Put these settings in it, entering the three private placeholders locally:

```dotenv
SNOWFLAKE_ACCOUNT=FYKURKL-NJC53016
SNOWFLAKE_USERNAME=ASINGH81
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=LIFEDATA
SNOWFLAKE_SCHEMA=LIFEDATA
SNOWFLAKE_CAMPUS=UMD
SNOWFLAKE_SEARCH_SERVICE=TERPLINK_SEARCH
SNOWFLAKE_SEARCH_TOKEN=YOUR_PRIVATE_SEARCH_TOKEN
SNOWFLAKE_BACKEND_ENABLED=true
SNOWFLAKE_APP_ROLE=TERPLINK_DATA_APP
SNOWFLAKE_APP_TOKEN=YOUR_PRIVATE_DATA_TOKEN
SESSION_SECRET=YOUR_LOCALLY_GENERATED_SECRET
COOKIE_SECURE=false
```

These settings connect persistence and AI discovery. The original announcement-prefill credentials are separate (see .env.example); do not reuse a read-only search token for AI_COMPLETE.

Never upload .env.local to GitHub. Use true for COOKIE_SECURE only when running behind HTTPS. Keep the same SESSION_SECRET on restart to preserve guest profiles.

## 4. Run

```sh
npm ci
npm run dev
```

Restart the process whenever environment settings change. Open http://localhost:3000. The strip should read **Shared campus catalog · Private guest profile**. If it says Campus demo, check SNOWFLAKE_BACKEND_ENABLED. If it errors, copy only the error text, not tokens.

## 5. Check the flow

1. Edit Profile, save, reload. Your changes should remain.
2. Create a group, publish, check Discover. Another teammate connecting to this same app/database can use Refresh catalog to see it.
3. Save a card with Interested; it should appear in Saved and remain after reload.
4. Set CS or K-pop interests and click Personalize with AI. Previously swiped cards should be excluded.
5. New listings may take up to the search refresh interval to appear in AI results. They appear in the normal catalog immediately.
6. Reset profile clears only your guest's profile and decisions; published shared cards remain.

## 6. Push for team review

If you have a local clone, copy the updated project files into it while preserving .git and your private .env.local. Do not copy node_modules or .next. Then:

```sh
 git switch -c finish-events-groups
 git add .
 git diff --cached --stat
 git commit -m "Complete Snowflake events and groups backend"
 git push -u origin finish-events-groups
```

Review the staged files before committing: no secrets should be listed. Open the repository on GitHub and choose Compare & pull request. Your teammates can review before merging. The delivered patch can alternatively be applied to the exact uploaded baseline using git apply; check for newer team changes first.
