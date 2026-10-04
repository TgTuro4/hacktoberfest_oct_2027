import "server-only";
import { decodeSearchResults, searchFilter, type SearchInput } from "../recommendations";

export class SearchServiceError extends Error {
  constructor(public code: "unconfigured" | "failed" | "timeout") { super(code); }
}

export async function recommend(input: SearchInput) {
  const env = process.env;
  if (!env.SNOWFLAKE_ACCOUNT || !env.SNOWFLAKE_SEARCH_TOKEN) throw new SearchServiceError("unconfigured");
  // Account/identifiers are server configuration, never caller-controlled URLs.
  if (!/^[a-z0-9][a-z0-9_-]*$/i.test(env.SNOWFLAKE_ACCOUNT)) throw new SearchServiceError("failed");
  const database = env.SNOWFLAKE_DATABASE || "LIFEDATA";
  const schema = env.SNOWFLAKE_SCHEMA || "LIFEDATA";
  const service = env.SNOWFLAKE_SEARCH_SERVICE || "TERPLINK_SEARCH";
  if (![database, schema, service].every(v => /^[a-z_][a-z0-9_]*$/i.test(v))) throw new SearchServiceError("failed");
  const campus = env.SNOWFLAKE_CAMPUS || "UMD";
  const url = `https://${env.SNOWFLAKE_ACCOUNT.toLowerCase()}.snowflakecomputing.com/api/v2/databases/${database.toUpperCase()}/schemas/${schema.toUpperCase()}/cortex-search-services/${service.toUpperCase()}:query`;
  const now = new Date();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(url, {
      method: "POST", cache: "no-store", redirect: "error", signal: controller.signal,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.SNOWFLAKE_SEARCH_TOKEN}`, "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN" },
      body: JSON.stringify({ query: input.query, columns: ["ITEM_ID", "ITEM_TYPE", "TITLE", "DESCRIPTION", "TAGS", "CAMPUS", "STARTS_AT", "IS_ACTIVE", "LOCATION", "MEETING_DETAILS", "IS_DEMO", "CREATED_AT"], filter: searchFilter(input, campus, now), limit: 50 }),
    });
    if (!response.ok) throw new SearchServiceError("failed");
    return decodeSearchResults(await response.json(), input, campus, now);
  } catch {
    throw new SearchServiceError(controller.signal.aborted ? "timeout" : "failed");
  } finally { clearTimeout(timer); }
}
