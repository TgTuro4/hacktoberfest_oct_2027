import { test } from "node:test";
import assert from "node:assert/strict";
import { decodeSearchResults, mergeSearchCards, parseSearchInput, searchFilter } from "../lib/recommendations";

const now = new Date("2026-10-04T17:00:00Z");
const request = (changes = {}) => ({ profile: { major: "Computer Science", bio: "Python projects", interests: ["AI"] }, kind: "all", excludedIds: [], ...changes });
const card = (changes = {}) => ({ ITEM_ID: "event:1", ITEM_TYPE: "event", TITLE: "AI Hackathon", DESCRIPTION: "Build Python projects", TAGS: "AI, Python, AI", CAMPUS: "UMD", STARTS_AT: "2026-10-05T22:00:00+00:00", IS_ACTIVE: 1, LOCATION: "Iribe Center", MEETING_DETAILS: "", IS_DEMO: true, CREATED_AT: "2026-10-04T12:00:00Z", ...changes });

test("query uses interests, major and bio without requiring or transmitting a name", () => {
  const input = parseSearchInput(request());
  assert.match(input.query, /Computer Science/);
  assert.match(input.query, /Interests: AI/);
  assert.match(input.query, /Python projects/);
});
test("invalid profiles and unbounded requests are rejected", () => {
  for (const body of [null, request({ kind: "people" }), request({ excludedIds: Array(501).fill("x") }), request({ profile: { major: "", bio: "", interests: [] } }), request({ profile: { major: "CS", bio: "", interests: [123] } })]) {
    assert.throws(() => parseSearchInput(body));
  }
});
test("search filter excludes only namespaced remote IDs and respects campus and type", () => {
  const input = parseSearchInput(request({ kind: "group", excludedIds: ["demo-1", "snowflake:group:7"] }));
  const serialized = JSON.stringify(searchFilter(input, "UMD", now));
  assert.match(serialized, /group:7/);
  assert.doesNotMatch(serialized, /demo-1/);
  assert.match(serialized, /STARTS_AT/);
  assert.match(serialized, /IS_ACTIVE/);
  assert.match(serialized, /UMD/);
});
test("decoding preserves rank, distinguishes event/group IDs, and converts campus time", () => {
  const items = decodeSearchResults({ results: [card(), card({ ITEM_ID: "group:1", ITEM_TYPE: "group", STARTS_AT: null })] }, parseSearchInput(request()), "UMD", now);
  assert.deepEqual(items.map(v => v.id), ["snowflake:event:1", "snowflake:group:1"]);
  assert.equal(items[0].date, "2026-10-05");
  assert.equal(items[0].time, "18:00");
  assert.deepEqual(items[0].tags, ["AI", "Python"]);
  assert.equal(items[1].date, "");
  assert.equal(items[0].demo, true);
  assert.equal(items[0].location, "Iribe Center");
});
test("decoding rejects cancelled, past, missing-date, wrong-campus and swiped cards", () => {
  const input = parseSearchInput(request({ excludedIds: ["snowflake:event:1"] }));
  const records = [card(), card({ ITEM_ID: "event:2", IS_ACTIVE: 0 }), card({ ITEM_ID: "event:3", STARTS_AT: "2026-10-03T12:00:00Z" }), card({ ITEM_ID: "event:4", CAMPUS: "Other" }), card({ ITEM_ID: "event:5", STARTS_AT: null })];
  assert.deepEqual(decodeSearchResults({ results: records }, input, "UMD", now), []);
});
test("duplicate search IDs are removed without changing order", () => {
  const items = decodeSearchResults({ results: [card(), card(), card({ ITEM_ID: "event:2" })] }, parseSearchInput(request()), "UMD", now);
  assert.equal(items.length, 2);
  assert.equal(items[1].id, "snowflake:event:2");
});
test("malformed service results fail rather than inventing cards", () => {
  assert.throws(() => decodeSearchResults({ results: [card({ TITLE: 99 })] }, parseSearchInput(request()), "UMD", now));
});
test("merging refreshes existing remote cards while keeping local creations and bookmarks' IDs", () => {
  const remote = decodeSearchResults({ results: [card()] }, parseSearchInput(request()), "UMD", now)[0];
  const local = { ...remote, id: "local-created", title: "My club" };
  const merged = mergeSearchCards([local, remote], [{ ...remote, title: "Updated" }]);
  assert.equal(merged.length, 2);
  assert.equal(merged[0].title, "My club");
  assert.equal(merged[1].title, "Updated");
});
