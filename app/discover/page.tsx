"use client";

import Link from "next/link";
import { useState } from "react";
import { useDemo } from "@/components/demo-provider";
import { SwipeCard } from "@/components/swipe-card";
import { Icon } from "@/components/icon";
import type { ItemKind } from "@/lib/types";

export default function DiscoverPage() {
  const { state, decide, undoDecision } = useDemo();
  const [filter, setFilter] = useState<"all" | ItemKind>("all");
  const [announcement, setAnnouncement] = useState("");
  // Cards decided this visit, newest last, so the back button can walk them back in order.
  const [history, setHistory] = useState<string[]>([]);
  const [pinned, setPinned] = useState<string | null>(null);
  if (!state) return null;

  const available = state.items
    .filter(item => !state.decisions[item.id] && (filter === "all" || item.kind === filter))
    .sort((a, b) => Number(b.id === pinned) - Number(a.id === pinned));
  const [current, next] = available;

  function goBack() {
    const lastId = history[history.length - 1];
    const last = state?.items.find(item => item.id === lastId);
    if (!last || !undoDecision(last.id)) return;
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
      {current ? (
        <SwipeCard
          key={`${filter}-${current.id}`}
          item={current}
          next={next}
          canUndo={history.length > 0}
          onUndo={goBack}
          onDecision={decision => {
            const success = decide(current.id, decision);
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
