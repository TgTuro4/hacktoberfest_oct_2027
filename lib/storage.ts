import { freshDemo } from "./seeds";
import type { DemoState } from "./types";

// One namespaced key; resetting never touches unrelated browser storage.
export const STORAGE_KEY = "terplink.demo.v1";

export function readDemo(storage: Pick<Storage, "getItem" | "setItem">): DemoState {
  const stored = storage.getItem(STORAGE_KEY);
  if (stored !== null) {
    const value: unknown = JSON.parse(stored);
    if (!isDemoState(value)) throw new Error("Saved TerpLink data is unreadable. Reset the demo to start fresh.");
    return value;
  }
  const initial = freshDemo();
  storage.setItem(STORAGE_KEY, JSON.stringify(initial));
  return initial;
}

function isDemoState(value: unknown): value is DemoState {
  if (typeof value !== "object" || value === null) return false;
  const state = value as DemoState;
  if (state.version !== 1 || !Array.isArray(state.items) || !state.profile || !state.decisions || typeof state.decisions !== "object" || Array.isArray(state.decisions)) return false;
  const string = (v: unknown) => typeof v === "string";
  const strings = (v: unknown) => Array.isArray(v) && v.every(string);
  return state.items.every(item => item && (item.kind === "group" || item.kind === "event") && [item.id, item.title, item.description, item.location, item.date, item.time, item.meetingDetails, item.createdAt].every(string) && strings(item.tags) && typeof item.demo === "boolean" && Number.isInteger(item.color))
    && [state.profile.name, state.profile.major, state.profile.bio, state.profile.availability].every(string)
    && strings(state.profile.interests)
    && Object.values(state.decisions).every(v => v === "pass" || v === "interested");
}

export function writeDemo(storage: Pick<Storage, "setItem">, state: DemoState): void {
  storage.setItem(STORAGE_KEY, JSON.stringify(state));
}
