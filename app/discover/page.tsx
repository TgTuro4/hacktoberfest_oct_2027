"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useDemo } from "@/components/demo-provider";
import { SwipeCard } from "@/components/swipe-card";
import { Icon } from "@/components/icon";
import type { CampusItem, ItemKind } from "@/lib/types";

export default function DiscoverPage() {
  const { state, decide, importSearchCards, resetVersion,mode,refresh,pending } = useDemo();
  const [filter, setFilter] = useState<"all" | ItemKind>("all");
  const [announcement, setAnnouncement] = useState("");
  const [rankedIds, setRankedIds] = useState<string[] | null>(null);
  const [searchMessage, setSearchMessage] = useState("");
  const [searching, setSearching] = useState(false);
  const generation = useRef(0);
  const profileKey = JSON.stringify(state?.profile);
  useEffect(() => {
    generation.current += 1;
    setRankedIds(null);
    setSearchMessage("");
    setSearching(false);
  }, [profileKey, filter, resetVersion]);
  useEffect(() => () => { generation.current += 1; }, []);
  if (!state) return null;

  async function personalize() {
    if (!state) return;
    const requestGeneration = ++generation.current;
    setSearching(true);
    setSearchMessage("");
    try {
      const response = await fetch("/api/recommendations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: { major: state.profile.major, bio: state.profile.bio, interests: state.profile.interests }, kind: filter, excludedIds: Object.keys(state.decisions) }),
      });
      const result = await response.json();
      if (requestGeneration !== generation.current) return;
      if (!response.ok) throw new Error(result.error || "AI search is unavailable.");
      const items = result.items as CampusItem[];
      if (!Array.isArray(items) || result.source !== "snowflake") throw new Error("AI search returned an unreadable response.");
      if (!importSearchCards(items)) throw new Error("The recommendations could not be saved in this browser.");
      setRankedIds(items.map(item => item.id));
      setSearchMessage(items.length ? "Personalized with Snowflake AI. Your profile interests were used to rank these cards." : "No matching cards in this catalog. Try another feed or update your interests.");
    } catch (error) {
      if (requestGeneration === generation.current) setSearchMessage(error instanceof Error ? error.message : "AI search is unavailable.");
    } finally {
      if (requestGeneration === generation.current) setSearching(false);
    }
  }

  const rankedCards = rankedIds === null ? state.items : rankedIds.map(id => state.items.find(item => item.id === id)).filter((item): item is CampusItem => Boolean(item));
  const available = rankedCards.filter(item =>
    !state.decisions[item.id] && (mode !== "snowflake" || !item.demo) && item.isActive !== false && (!item.startsAt || new Date(item.startsAt).getTime() >= Date.now()) && (filter === "all" || item.kind === filter)
  );
  const current = available[0];

  return (
    <section className="discovery-feed" aria-label="Swipe discovery">
      <h1 className="discovery-heading">Discover.</h1>
      <div className="feed-toolbar">
        <div className="segmented" role="group" aria-label="Filter discovery">
          {(["all", "group", "event"] as const).map(value => (
            <button
              key={value}
              aria-pressed={filter === value}
              className={filter === value ? "selected" : ""}
              onClick={() => setFilter(value)}
            >
              {value === "all" ? "All" : value === "group" ? "Groups" : "Events"}
            </button>
          ))}
        </div>
        <span className="feed-count">{available.length} to explore</span>
      </div>
      <div className="ai-discovery-controls">
        <button className="button primary" disabled={searching} onClick={personalize}>{searching ? "Finding your matches…" : "Personalize with AI"}</button>
        {rankedIds !== null && <button className="text-link" onClick={() => { generation.current += 1; setRankedIds(null); setSearchMessage(""); setSearching(false); }}>{mode === "snowflake" ? "Browse shared catalog" : "Browse all local cards"}</button>}
        {mode === "snowflake" && <button className="text-link" disabled={pending || searching} onClick={async () => { generation.current++;setRankedIds(null);setSearchMessage("");await refresh(); }}>Refresh catalog</button>}
        <p>Use your major, bio and interests to search the campus catalog.</p>
        {searchMessage && <p role="status">{searchMessage}</p>}
      </div>
      {current ? (
        <SwipeCard
          key={`${filter}-${current.id}`}
          item={current}
          onDecision={async decision => {
            const success = await decide(current.id, decision);
            if (success) {
              setAnnouncement(`${current.title}: ${decision === "interested" ? "saved to your interested list" : "passed"}.`);
            }
            return success;
          }}
        />
      ) : (
        <div className="empty-state feed-empty">
          <div className="empty-icon"><Icon name="check" size={32} /></div>
          <p className="eyebrow">ALL CAUGHT UP</p>
          <h2>You made the rounds.</h2>
          <p>No more {filter === "all" ? "cards" : `${filter}s`} for now. Visit your saved finds or create something for your campus.</p>
          <Link className="button primary" href="/saved">View saved finds <Icon name="arrow" size={18} /></Link>
          <Link href="/create" className="text-link">Create a group or event</Link>
        </div>
      )}
      <span className="sr-only" role="status" aria-live="polite">{announcement}</span>
    </section>
  );
}
