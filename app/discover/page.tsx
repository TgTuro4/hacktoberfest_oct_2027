"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useDemo } from "@/components/demo-provider";
import { SwipeCard } from "@/components/swipe-card";
import { Icon } from "@/components/icon";
import type { CampusItem, ItemKind } from "@/lib/types";

type AiStatus =
  | { kind: "idle" }
  | { kind: "ranking" }
  | { kind: "ranked"; count: number }
  | { kind: "empty" }
  | { kind: "unavailable"; detail: string };

export default function DiscoverPage() {
  const { state, decide, undoDecision, importSearchCards, resetVersion, mode, refresh, pending } = useDemo();
  const [filter, setFilter] = useState<"all" | ItemKind>("all");
  const [announcement, setAnnouncement] = useState("");
  // Cards decided this visit, newest last, so the back button can walk them back in order.
  const [history, setHistory] = useState<string[]>([]);
  const [pinned, setPinned] = useState<string | null>(null);
  // AI ranking: ids in the order Snowflake Cortex Search ranked them for this profile.
  const [rankedIds, setRankedIds] = useState<string[] | null>(null);
  const [ai, setAi] = useState<AiStatus>({ kind: "idle" });
  const generation = useRef(0);
  const latest = useRef(state);
  latest.current = state;
  const profileKey = JSON.stringify(state?.profile ?? null);
  const loaded = state !== null;

  async function personalize() {
    const snapshot = latest.current;
    if (!snapshot) return;
    const run = ++generation.current;
    setAi({ kind: "ranking" });
    try {
      const response = await fetch("/api/recommendations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: { major: snapshot.profile.major, bio: snapshot.profile.bio, interests: snapshot.profile.interests }, kind: filter, excludedIds: Object.keys(snapshot.decisions) }),
      });
      const result = await response.json();
      if (run !== generation.current) return;
      if (!response.ok) throw new Error(result.error || "AI search is unavailable.");
      const items = result.items as CampusItem[];
      if (!Array.isArray(items) || result.source !== "snowflake") throw new Error("AI search returned an unreadable response.");
      if (!items.length) { setRankedIds(null); setAi({ kind: "empty" }); return; }
      if (!importSearchCards(items)) throw new Error("The recommendations could not be saved in this browser.");
      setRankedIds(items.map(item => item.id));
      setAi({ kind: "ranked", count: items.length });
    } catch (error) {
      if (run !== generation.current) return;
      setRankedIds(null);
      setAi({ kind: "unavailable", detail: error instanceof Error ? error.message : "AI search is unavailable." });
    }
  }

  // Analyze automatically whenever Discover opens, the feed filter changes, or the profile/reset changes.
  useEffect(() => {
    if (!loaded) return;
    setRankedIds(null);
    void personalize();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, profileKey, filter, resetVersion]);
  useEffect(() => () => { generation.current += 1; }, []);

  if (!state) return null;

  // AI picks first (in ranked order), then everything else, so the deck never ends early.
  const rankedSet = new Set(rankedIds ?? []);
  const ordered = rankedIds === null ? state.items : [
    ...rankedIds.map(id => state.items.find(item => item.id === id)).filter((item): item is CampusItem => Boolean(item)),
    ...state.items.filter(item => !rankedSet.has(item.id)),
  ];
  const available = ordered
    .filter(item => !state.decisions[item.id]
      && (mode !== "snowflake" || !item.demo)
      && item.isActive !== false
      && (!item.startsAt || new Date(item.startsAt).getTime() >= Date.now())
      && (filter === "all" || item.kind === filter))
    .sort((a, b) => Number(b.id === pinned) - Number(a.id === pinned));
  const [current, next] = available;

  async function goBack() {
    const lastId = history[history.length - 1];
    const last = state?.items.find(item => item.id === lastId);
    if (!last || !await undoDecision(last.id)) return;
    setHistory(list => list.slice(0, -1));
    setPinned(last.id);
    if (filter !== "all" && last.kind !== filter) setFilter("all");
    setAnnouncement(`Back to ${last.title}.`);
  }

  return (
    <section className="discovery-feed" aria-label="Swipe discovery">
      <div className="feed-toolbar">
        <h1 className="discovery-heading">Discover</h1>
        <div className="chip-row" role="group" aria-label="Filter discovery">
          {(["all", "group", "event"] as const).map(value => (
            <button
              key={value}
              aria-pressed={filter === value}
              className={`chip ${filter === value ? "selected" : ""}`}
              onClick={() => setFilter(value)}
            >
              {value === "all" ? "All" : value === "group" ? "Groups" : "Events"}
            </button>
          ))}
        </div>
        <span className="feed-count">{available.length} left</span>
      </div>

      <div className={`ai-status ai-${ai.kind}`} role="status" aria-live="polite">
        <Icon name="sparkles" size={16} strokeWidth={2} className="ai-icon" />
        {ai.kind === "ranking" && <span>Finding your matches…</span>}
        {ai.kind === "ranked" && <span>Ranked for you by Snowflake AI</span>}
        {ai.kind === "empty" && <span>No AI matches for this feed, showing all cards</span>}
        {ai.kind === "unavailable" && <span title={ai.detail}>AI ranking isn’t connected, showing all cards</span>}
        {ai.kind === "idle" && <span>Showing all cards</span>}
        <span className="ai-actions">
          {(ai.kind === "unavailable" || ai.kind === "empty" || ai.kind === "idle") && <button className="ai-link" onClick={() => void personalize()}>{ai.kind === "idle" ? "Rank with AI" : "Retry"}</button>}
          {ai.kind === "ranked" && <button className="ai-link" onClick={() => { generation.current += 1; setRankedIds(null); setAi({ kind: "idle" }); }}>Show all</button>}
          {mode === "snowflake" && ai.kind !== "ranking" && <button className="ai-link" disabled={pending} onClick={async () => { generation.current += 1; setRankedIds(null); await refresh(); void personalize(); }}>Refresh</button>}
        </span>
      </div>

      {current ? (
        <SwipeCard
          key={`${filter}-${current.id}`}
          item={current}
          next={next}
          canUndo={history.length > 0}
          onUndo={goBack}
          onDecision={async decision => {
            const success = await decide(current.id, decision);
            if (success) {
              setHistory(list => [...list, current.id]);
              setPinned(null);
              setAnnouncement(`${current.title}: ${decision === "interested" ? "saved" : "passed"}.`);
            }
            return success;
          }}
        />
      ) : (
        <div className="empty-state feed-empty">
          <div className="empty-icon"><Icon name="check" size={32} /></div>
          <h2>You made the rounds.</h2>
          <p>No more {filter === "all" ? "cards" : `${filter}s`} for now. Look back at what you saved, or post something for your campus.</p>
          <Link className="button primary" href="/saved">See what you saved</Link>
          <Link href="/create" className="text-link">Create a group or event</Link>
        </div>
      )}
      <span className="sr-only" role="status" aria-live="polite">{announcement}</span>
    </section>
  );
}
