import { afterEach, test, mock } from "node:test";
import assert from "node:assert/strict";
import { recommend, SearchServiceError } from "../../lib/server/search";
import { POST } from "../../app/api/recommendations/route";

const keys = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_SEARCH_TOKEN", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA", "SNOWFLAKE_SEARCH_SERVICE", "SNOWFLAKE_CAMPUS"];
const original = Object.fromEntries(keys.map(key => [key, process.env[key]]));
afterEach(() => { mock.restoreAll(); for (const key of keys) { if (original[key] === undefined) delete process.env[key]; else process.env[key] = original[key]; } });
function configure() {
  process.env.SNOWFLAKE_ACCOUNT = "example-account";
  process.env.SNOWFLAKE_SEARCH_TOKEN = "test-token-not-a-secret";
  for (const key of keys.slice(2)) delete process.env[key];
}
const input = { query: "Python", kind: "all" as const, excludedIds: [] };

test("server sends the REST search request to the configured service with private authentication", async () => {
  configure();
  const fetchMock = mock.method(globalThis, "fetch", async (url: string | URL | Request, options?: RequestInit) => {
    assert.equal(String(url), "https://example-account.snowflakecomputing.com/api/v2/databases/LIFEDATA/schemas/LIFEDATA/cortex-search-services/TERPLINK_SEARCH:query");
    const body = JSON.parse(String(options?.body));
    assert.equal(body.query, "Python");
    assert.ok(body.columns.includes("LOCATION"));
    assert.equal(body.limit, 50);
    assert.equal(options?.cache, "no-store");
    assert.equal((options?.headers as Record<string, string>).Authorization, "Bearer test-token-not-a-secret");
    return Response.json({ results: [] });
  });
  assert.deepEqual(await recommend(input), []);
  assert.equal(fetchMock.mock.callCount(), 1);
});
test("unconfigured server does not call Snowflake", async () => {
  configure(); delete process.env.SNOWFLAKE_SEARCH_TOKEN;
  const fetchMock = mock.method(globalThis, "fetch", async () => { throw new Error("unexpected"); });
  await assert.rejects(recommend(input), (error: unknown) => error instanceof SearchServiceError && error.code === "unconfigured");
  assert.equal(fetchMock.mock.callCount(), 0);
});
test("upstream authentication failure does not expose provider diagnostics", async () => {
  configure();
  mock.method(globalThis, "fetch", async () => new Response("private upstream diagnostics", { status: 401 }));
  const response = await POST(new Request("http://localhost/api/recommendations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile: { major: "CS", bio: "", interests: ["AI"] }, kind: "all", excludedIds: [] }) }));
  assert.equal(response.status, 502);
  const text = await response.text();
  assert.doesNotMatch(text, /private upstream|test-token/);
});
test("route bounds streamed input and rejects invalid JSON", async () => {
  const oversized = await POST(new Request("http://localhost/api/recommendations", { method: "POST", headers: { "Content-Type": "application/json" }, body: "x".repeat(128001) }));
  assert.equal(oversized.status, 413);
  const malformed = await POST(new Request("http://localhost/api/recommendations", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{" }));
  assert.equal(malformed.status, 400);
});
