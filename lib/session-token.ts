import { createHmac, timingSafeEqual } from "node:crypto";
const AGE = 30 * 24 * 60 * 60;
export function signGuest(id: string, secret: string, now = Math.floor(Date.now()/1000)) {
  if (secret.length < 32) throw new Error("Session secret must contain at least 32 characters.");
  const payload = `${id}.${now + AGE}`;
  return `${payload}.${createHmac("sha256", secret).update(payload).digest("base64url")}`;
}
export function verifyGuest(token: string | undefined, secret: string, now = Math.floor(Date.now()/1000)): string | null {
  if (!token || secret.length < 32 || token.length > 150) return null;
  const [id, exp, signature, extra] = token.split(".");
  if (extra || !/^[0-9a-f-]{36}$/i.test(id || "") || !/^\d{10}$/.test(exp || "") || Number(exp) <= now || Number(exp) > now + AGE || !signature) return null;
  const expected = createHmac("sha256",secret).update(`${id}.${exp}`).digest("base64url");
  const a = Buffer.from(expected), b = Buffer.from(signature);
  return a.length === b.length && timingSafeEqual(a,b) ? id : null;
}
