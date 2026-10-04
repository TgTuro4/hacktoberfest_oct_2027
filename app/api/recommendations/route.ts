import { parseSearchInput } from "@/lib/recommendations";
import { recommend, SearchServiceError } from "@/lib/server/search";

import { backendEnabled,withGuestDatabase } from "@/lib/server/database";
import { guestSession } from "@/lib/server/guest";
import { ensureUser,readState,recheckResults } from "@/lib/server/store";
import { sameOrigin } from "@/lib/server/http";

export const runtime = "nodejs";
const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { "Cache-Control": "no-store" } });

export async function POST(request: Request) {
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) return json({ error: "Send profile details as JSON." }, 415);
  let body: unknown;
  try {
    if (!request.body) throw new Error("empty");
    const reader = request.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        size += chunk.value.byteLength;
        if (size > 128000) { await reader.cancel(); return json({ error: "Request is too large." }, 413); }
        chunks.push(chunk.value);
      }
    } finally { reader.releaseLock(); }
    body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch { return json({ error: "Invalid JSON request." }, 400); }
  let input;
  try { input = parseSearchInput(body); }
  catch { return json({ error: "Check your profile, feed type and swipe history. Add interests before searching; at most 500 swiped cards are supported in this demo." }, 400); }
  try {
    let items;
    if (backendEnabled()) {
      sameOrigin(request);
      const key=await guestSession();
      items=await withGuestDatabase(key,async q=> {
        const userId=await ensureUser(q,key);
        const state=await readState(q,userId);
        const serverInput=parseSearchInput({profile:state.profile,kind:input.kind,excludedIds:Object.keys(state.decisions).slice(-500)});
        return recheckResults(q,await recommend(serverInput),userId);
      });
    } else items = await recommend(input);
    return json({ source: "snowflake", items });
  } catch (error) {
    if (error instanceof SearchServiceError && error.code === "unconfigured") return json({ error: "AI discovery is not connected yet. Your team needs to configure the server’s Snowflake search access token. You can still explore the local cards." }, 503);
    if (error instanceof SearchServiceError && error.code === "timeout") return json({ error: "AI search took too long. Try again." }, 504);
    return json({ error: "AI search is unavailable. Ask your team to check the search service, server credentials and permissions." }, 502);
  }
}
