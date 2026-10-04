import "server-only";
import { cookies } from "next/headers";
import { randomUUID } from "node:crypto";
import { signGuest, verifyGuest } from "../session-token";
const COOKIE="terplink.guest.v1";
export async function guestSession(create = false) {
  const secret=process.env.SESSION_SECRET || "";
  if (secret.length<32) throw new Error("Session configuration missing.");
  const store=await cookies();
  let id=verifyGuest(store.get(COOKIE)?.value,secret);
  if (!id && !create) throw new Error("Open the app to start a guest session.");
  if (!id) {
    id=randomUUID();
    store.set(COOKIE,signGuest(id,secret), { httpOnly:true, sameSite:"lax", secure:process.env.COOKIE_SECURE === "true", path:"/", maxAge:30*24*60*60 });
  }
  return id;
}
