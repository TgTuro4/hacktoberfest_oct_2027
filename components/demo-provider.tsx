"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { readDemo, writeDemo } from "@/lib/storage";
import { freshDemo } from "@/lib/seeds";
import type { CampusItem, Decision, DemoState, Draft, Profile } from "@/lib/types";

interface DemoContextValue {
  state: DemoState | null;
  ready: boolean;
  resetVersion: number;
  error: string;
  addItem: (draft: Draft) => boolean;
  decide: (id: string, decision: Decision) => boolean;
  undoDecision: (id: string) => boolean;
  saveProfile: (profile: Profile) => boolean;
  reset: () => boolean;
}
const DemoContext = createContext<DemoContextValue | null>(null);

export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DemoState | null>(null);
  const current = useRef<DemoState | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [resetVersion, setResetVersion] = useState(0);

  useEffect(() => {
    try {
      current.current = readDemo(window.localStorage);
      setState(current.current);
    } catch {
      setError("We couldn’t open your local demo. Browser storage may be blocked, full, or unreadable. Enable storage or reset the demo to retry.");
    }
    setReady(true);
  }, []);

  function commit(next: DemoState): boolean {
    try {
      writeDemo(window.localStorage, next);
      current.current = next;
      setState(next);
      setError("");
      return true;
    } catch {
      setError("Your changes couldn’t be saved. Check that browser storage is enabled and has space, then try again.");
      return false;
    }
  }

  const value: DemoContextValue = {
    state, ready, error, resetVersion,
    addItem(draft) {
      if (!current.current) return false;
      const item: CampusItem = { ...draft, title: draft.title.trim(), description: draft.description.trim(), location: draft.location.trim(), meetingDetails: draft.meetingDetails.trim(), id: crypto.randomUUID(), demo: false, color: current.current.items.length % 4, createdAt: new Date().toISOString() };
      return commit({ ...current.current, items: [item, ...current.current.items] });
    },
    decide(id, decision) {
      if (!current.current) return false;
      return commit({ ...current.current, decisions: { ...current.current.decisions, [id]: decision } });
    },
    undoDecision(id) {
      if (!current.current) return false;
      const { [id]: _removed, ...decisions } = current.current.decisions;
      return commit({ ...current.current, decisions });
    },
    saveProfile(profile) {
      return current.current ? commit({ ...current.current, profile }) : false;
    },
    reset() {
      const saved = commit(freshDemo());
      if (saved) setResetVersion(v => v + 1);
      return saved;
    },
  };
  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  const context = useContext(DemoContext);
  if (!context) throw new Error("useDemo must be used within DemoProvider");
  return context;
}
