import { backendEnabled, withGuestDatabase } from "@/lib/server/database";
import { guestSession } from "@/lib/server/guest";
import { ensureUser, readState } from "@/lib/server/store";
import { reply } from "@/lib/server/http";
export const runtime="nodejs";
export async function GET() {
  if(!backendEnabled())return reply({mode:"local"});
  try {const key=await guestSession(true);return reply({mode:"snowflake",state:await withGuestDatabase(key,async q=>readState(q,await ensureUser(q,key)))});}
  catch{return reply({error:"Could not load your Snowflake workspace. Check the server configuration and database migration, then retry."},503);}
}
