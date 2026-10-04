"use client";

import Link from "next/link";
import { useState } from "react";
import { useDemo } from "@/components/demo-provider";
import { CampusCard } from "@/components/campus-card";
import { Icon } from "@/components/icon";

export default function SavedPage() {
  const { state, decide,pending } = useDemo();
  const [message, setMessage] = useState("");
  if (!state) return null;
  const saved = state.items.filter(item => state.decisions[item.id] === "interested");
  return <section>
    <div className="page-heading"><p className="eyebrow">KEEP THE GOOD FINDS CLOSE</p><h1>Your kind of <em>things.</em></h1><p>{saved.length ? `${saved.length} ${saved.length === 1 ? "spark" : "sparks"} of interest. A little collection of what’s next.` : "When something catches your eye, save it here."}</p></div>
    <div className="notice subtle"><Icon name="bookmark" size={20} /><span>Saved means interested. It doesn’t confirm group membership or event registration.</span></div>
    <p role="status" className="status-message">{message}</p>
    {saved.length ? <div className="saved-grid">{saved.map(item => <div className="saved-item" key={item.id}><CampusCard item={item} compact /><button className="remove-button" aria-label={`Remove ${item.title} from saved`} disabled={pending} onClick={async () => { if (await decide(item.id, "pass")) setMessage(`${item.title} removed from saved.`); }}><Icon name="close" size={18} />Remove from saved</button></div>)}</div> : <div className="empty-state"><div className="empty-icon"><Icon name="bookmark" size={32} /></div><h2>A little room for possibility.</h2><p>Tap Interested or swipe right on a card to start your collection.</p><Link className="button primary" href="/discover">Find your next thing <Icon name="arrow" size={18} /></Link></div>}
  </section>;
}
