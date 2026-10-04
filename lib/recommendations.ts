import type { CampusItem, ItemKind } from "./types";

export interface SearchInput {
  query: string;
  kind: "all" | ItemKind;
  excludedIds: string[];
}
const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

export function parseSearchInput(body: unknown): SearchInput {
  if (!object(body) || !object(body.profile)) throw new Error("Invalid profile.");
  const p = body.profile;
  const text = (key: string, max: number) => {
    if (typeof p[key] !== "string" || p[key].length > max) throw new Error("Invalid profile field.");
    return p[key].trim();
  };
  const major = text("major", 200), bio = text("bio", 2000);
  if (!Array.isArray(p.interests) || p.interests.length > 30 || p.interests.some(v => typeof v !== "string" || v.length > 100)) throw new Error("Invalid interests.");
  const interests = p.interests.map(v => v.trim()).filter(Boolean);
  if (!major && !bio && !interests.length) throw new Error("Add a major, bio or interests to your profile first.");
  if (body.kind !== "all" && body.kind !== "event" && body.kind !== "group") throw new Error("Invalid feed type.");
  if (!Array.isArray(body.excludedIds) || body.excludedIds.length > 500 || body.excludedIds.some(v => typeof v !== "string" || v.length > 200)) throw new Error("Invalid excluded cards.");
  return { query: [major && `Major: ${major}`, interests.length && `Interests: ${interests.join(", ")}`, bio && `About me: ${bio}`].filter(Boolean).join(". "), kind: body.kind, excludedIds: [...new Set(body.excludedIds)] };
}

export function searchFilter(input: SearchInput, campus: string, now: Date) {
  const clauses: Record<string, unknown>[] = [
    { "@eq": { CAMPUS: campus } }, { "@eq": { IS_ACTIVE: 1 } },
    { "@or": [{ "@eq": { ITEM_TYPE: "group" } }, { "@gte": { STARTS_AT: now.toISOString() } }] },
  ];
  if (input.kind !== "all") clauses.push({ "@eq": { ITEM_TYPE: input.kind } });
  const seen = input.excludedIds.filter(id => id.startsWith("snowflake:")).map(id => id.slice(10));
  if (seen.length) clauses.push({ "@not": { "@or": seen.map(id => ({ "@eq": { ITEM_ID: id } })) } });
  return { "@and": clauses };
}

export function decodeSearchResults(value: unknown, input: SearchInput, campus: string, now: Date, includeUnavailable = false): CampusItem[] {
  if (!object(value) || !Array.isArray(value.results) || value.results.length > 5000) throw new Error("Invalid search response.");
  const seen = new Set(input.excludedIds);
  const items: CampusItem[] = [];
  for (const raw of value.results) {
    if (!object(raw)) throw new Error("Invalid search card.");
    const str = (key: string, max: number) => {
      if (typeof raw[key] !== "string" || raw[key].length > max) throw new Error("Invalid search field.");
      return raw[key].trim();
    };
    const rawId = str("ITEM_ID", 180), id = `snowflake:${rawId}`;
    const kind = str("ITEM_TYPE", 10);
    if (!rawId || (kind !== "event" && kind !== "group")) throw new Error("Invalid card identity.");
    const title = str("TITLE", 500), description = str("DESCRIPTION", 20000), rowCampus = str("CAMPUS", 200);
    if (!title) throw new Error("Missing card title.");
    if (rowCampus !== campus || (input.kind !== "all" && kind !== input.kind) || (!includeUnavailable && Number(raw.IS_ACTIVE) !== 1) || seen.has(id)) continue;
    let date = "", time = "";
    if (kind === "event") {
      if (typeof raw.STARTS_AT !== "string") continue;
      const start = new Date(raw.STARTS_AT);
      if (!Number.isFinite(start.getTime()) || (!includeUnavailable && start < now)) continue;
      const parts = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(start);
      const part = (type: string) => parts.find(p => p.type === type)?.value || "";
      date = `${part("year")}-${part("month")}-${part("day")}`;
      time = `${part("hour")}:${part("minute")}`;
    }
    const tags = [...new Set(str("TAGS", 1000).split(",").map(t => t.trim()).filter(Boolean))].slice(0, 8).map(t => t.slice(0, 30));
    const sourceMatch = /^Official listing: (https:\/\/[^\s]+)\n\n/.exec(description);
    const sourceUrl = sourceMatch?.[1];
    const cardDescription = sourceMatch ? description.slice(sourceMatch[0].length) : description;
    seen.add(id);
    // Dates are shown in the same campus timezone used by the existing cards.
    items.push({ id, kind, title, description: cardDescription.length > 2000 ? cardDescription.slice(0, 1999) + "…" : cardDescription, sourceUrl, allDay: cardDescription.includes("All-day event; check the official listing for attendance hours."), tags, date, time, location: str("LOCATION", 200), meetingDetails: str("MEETING_DETAILS", 300), demo: raw.IS_DEMO === true || raw.IS_DEMO === "true", color: items.length % 4, createdAt: typeof raw.CREATED_AT === "string" ? raw.CREATED_AT : now.toISOString(), isActive: Number(raw.IS_ACTIVE) === 1, startsAt: typeof raw.STARTS_AT === "string" ? raw.STARTS_AT : undefined });
  }
  return items;
}

export function mergeSearchCards(existing: CampusItem[], incoming: CampusItem[]): CampusItem[] {
  const replacements = new Map(incoming.map(item => [item.id, item]));
  const ids = new Set(existing.map(item => item.id));
  return [...incoming.filter(item => !ids.has(item.id)), ...existing.map(item => replacements.get(item.id) || item)];
}
