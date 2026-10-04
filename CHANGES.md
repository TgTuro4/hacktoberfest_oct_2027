# Completed events and groups delivery

This delivery extends the uploaded repository baseline `9557d06dccfc45ca227f9de69223c07fa6671dad`.

- Adds a Snowflake guest backend for profiles, normalized interests, event/group publishing and persistent swipes.
- Adds signed private guest cookies, validated bound SQL, transactions, retry-safe publishing keys, same-origin mutation checks and request size limits.
- Connects Cortex Search to the stored profile and swipe history; checks current catalog availability before displaying AI results.
- Updates the frontend to await writes, show failures, refresh shared listings and preserve browser demo mode when explicitly configured.
- Adds SQL scripts 01–06, environment placeholders, setup instructions, unit/server tests and browser regression tests.
- Preserves the original announcement-prefill feature and frontend design.

Login, people matching and production multi-instance deployment remain outside the agreed scope. No private credentials, installed dependencies or generated build files are delivered.
