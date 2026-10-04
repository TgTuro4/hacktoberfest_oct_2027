import { draftErrors, validDate, validTime } from "./validation";
import type { Draft, Profile } from "./types";
export function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid object.");
  return value as Record<string, unknown>;
}
function string(raw: Record<string, unknown>, key: string, max: number) {
  if (typeof raw[key] !== "string" || raw[key].length > max) throw new Error(`Invalid ${key}.`);
  return raw[key].trim();
}
function tags(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > 8 || value.some(v => typeof v !== "string" || !v.trim() || v.length > 30 || v.includes(","))) throw new Error("Invalid interests.");
  return [...new Set(value.map(v => v.trim()))];
}
export function profileInput(value: unknown): Profile {
  const raw = record(value);
  const profile = { name: string(raw,"name",80), major: string(raw,"major",100), bio: string(raw,"bio",400), availability: string(raw,"availability",200), interests: tags(raw.interests) };
  if (!profile.name) throw new Error("Add a display name.");
  return profile;
}
export function draftInput(value: unknown): Draft {
  const raw = record(value);
  if (raw.kind !== "event" && raw.kind !== "group") throw new Error("Invalid item kind.");
  const draft: Draft = { kind: raw.kind, title: string(raw,"title",100), description: string(raw,"description",2000), location: string(raw,"location",200), date: string(raw,"date",10), time: string(raw,"time",5), meetingDetails: string(raw,"meetingDetails",300), tags: tags(raw.tags) };
  if (draftErrors(draft).length) throw new Error("Complete the required card fields.");
  if (draft.kind === "event" && (!validDate(draft.date) || !validTime(draft.time))) throw new Error("Invalid schedule.");
  return draft;
}
export function catalogIdentity(id: unknown): { kind: "event" | "group"; numericId: string } {
  if (typeof id !== "string") throw new Error("Invalid card ID.");
  const match = /^snowflake:(event|group):([1-9]\d{0,18})$/.exec(id);
  if (!match) throw new Error("Invalid card ID.");
  return { kind: match[1] as "event" | "group", numericId: match[2] };
}
export function publishKey(value: unknown): string {
  if (typeof value !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) throw new Error("Invalid publish key.");
  return value;
}
