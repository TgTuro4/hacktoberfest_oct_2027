"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { readDemo, writeDemo } from "@/lib/storage";
import { freshDemo } from "@/lib/seeds";
import { mergeSearchCards } from "@/lib/recommendations";
import type { CampusItem, Decision, DemoState, Draft, Profile } from "@/lib/types";

/**
 * "local": demo data in this browser's localStorage.
 * "snowflake": the server reports a live backend; profile, swipes and publishing go through /api/*.
 */
export type DataMode = "local" | "snowflake";

interface DemoContextValue {
  state: DemoState | null;
  ready: boolean;
  resetVersion: number;
  error: string;
  mode: DataMode;
  pending: boolean;
  addItem: (draft: Draft) => Promise<boolean>;
  decide: (id: string, decision: Decision) => Promise<boolean>;
  undoDecision: (id: string) => Promise<boolean>;
  saveProfile: (profile: Profile) => Promise<boolean>;
  reset: () => Promise<boolean>;
  importSearchCards: (items: CampusItem[]) => boolean;
  refresh: () => Promise<void>;
}
const DemoContext = createContext<DemoContextValue | null>(null);

async function api(path: string, body?: unknown) {
  const response = await fetch(path, body === undefined
    ? { cache: "no-store" }
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "The server could not save this change.");
  return result;
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DemoState | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<DataMode>("local");
  const [pending, setPending] = useState(false);
  const [resetVersion, setResetVersion] = useState(0);
  const current = useRef<DemoState | null>(null);
  const live = useRef(false);
  const locked = useRef(false);
  const generation = useRef(0);
  // One idempotency key per draft, so retrying a failed publish never creates a duplicate.
  const attempts = useRef(new Map<string, string>());
  const initialRequest = useRef<ReturnType<typeof api> | null>(null);

  function publishState(next: DemoState) {
    current.current = next;
    setState(next);
    setError("");
  }

  async function refresh(cached?: ReturnType<typeof api>) {
    const version = ++generation.current;
    try {
      const result = await (cached || api("/api/state"));
      if (version !== generation.current) return;
      live.current = result.mode === "snowflake";
      setMode(live.current ? "snowflake" : "local");
      publishState(live.current ? result.state : readDemo(window.localStorage));
    } catch (err) {
      if (version === generation.current) setError(err instanceof Error ? err.message : "We couldn’t load your data. Retry.");
    } finally {
      if (version === generation.current) setReady(true);
    }
  }

  useEffect(() => {
    initialRequest.current ||= api("/api/state");
    void refresh(initialRequest.current);
    return () => { generation.current++; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function commit(next: DemoState) {
    try {
      if (!live.current) writeDemo(window.localStorage, next);
      publishState(next);
      return true;
    } catch {
      setError("Your changes couldn’t be saved. Check that browser storage is enabled and has space, then try again.");
      return false;
    }
  }

  // Serializes writes: one change at a time, and nothing is shown as saved until it is.
  async function change(work: () => Promise<boolean>) {
    if (locked.current || !current.current) return false;
    locked.current = true;
    setPending(true);
    try {
      return await work();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The change could not be saved.");
      return false;
    } finally {
      locked.current = false;
      setPending(false);
    }
  }

  const value: DemoContextValue = {
    state, ready, error, mode, pending, resetVersion, refresh: () => refresh(),
    addItem(draft) {
      return change(async () => {
        let item: CampusItem;
        if (live.current) {
          const fingerprint = JSON.stringify(draft);
          const key = attempts.current.get(fingerprint) || crypto.randomUUID();
          attempts.current.set(fingerprint, key);
          item = (await api("/api/items", { draft, key })).item;
          attempts.current.delete(fingerprint);
        } else {
          item = { ...draft, title: draft.title.trim(), description: draft.description.trim(), location: draft.location.trim(), meetingDetails: draft.meetingDetails.trim(), id: crypto.randomUUID(), demo: false, color: current.current!.items.length % 4, createdAt: new Date().toISOString() };
        }
        return commit({ ...current.current!, items: mergeSearchCards(current.current!.items, [item]) });
      });
    },
    decide(id, decision) {
      return change(async () => {
        if (live.current) await api("/api/swipes", { id, decision });
        return commit({ ...current.current!, decisions: { ...current.current!.decisions, [id]: decision } });
      });
    },
    undoDecision(id) {
      return change(async () => {
        if (live.current) await api("/api/swipes", { id, decision: "clear" });
        const { [id]: _removed, ...decisions } = current.current!.decisions;
        return commit({ ...current.current!, decisions });
      });
    },
    saveProfile(profile) {
      return change(async () => {
        if (live.current) await api("/api/profile", profile);
        return commit({ ...current.current!, profile });
      });
    },
    async reset() {
      if (!current.current) {
        try { writeDemo(window.localStorage, freshDemo()); } catch { setError("Browser storage is unavailable."); return false; }
        await refresh();
        return true;
      }
      return change(async () => {
        const next = live.current ? (await api("/api/reset", {})).state : freshDemo();
        const saved = commit(next);
        if (saved) setResetVersion(v => v + 1);
        return saved;
      });
    },
    importSearchCards(items) {
      return current.current ? commit({ ...current.current, items: mergeSearchCards(current.current.items, items) }) : false;
    },
  };
  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  const context = useContext(DemoContext);
  if (!context) throw new Error("useDemo must be used within DemoProvider");
  return context;
}
