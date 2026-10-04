"use client";

import Link from "next/link";
import { useDemo } from "@/components/demo-provider";
import { Icon } from "@/components/icon";

export default function HomePage() {
  const { state } = useDemo();
  if (!state) return null;
  const available = state.items.filter(item => !state.decisions[item.id]);
  const saved = Object.values(state.decisions).filter(d => d === "interested").length;
  const firstName = state.profile.name.trim().split(/\s+/)[0];
  return (
    <section className="home-intro">
      <p className="eyebrow"><span />YOUR CAMPUS. YOUR PEOPLE.</p>
      <h1>Less scrolling.<br />More <em>belonging.</em></h1>
      <p className="intro-copy">Hey {firstName || "Terp"}, there’s a whole campus beyond your usual circle. Find a group, try something new, and make it yours.</p>
      <Link href="/discover" className="button primary home-discover-link">
        Start discovering <Icon name="arrow" size={20} />
      </Link>
      <div className="intro-rule" />
      <div className="discovery-stats"><div><strong>{available.length.toString().padStart(2, "0")}</strong><span>left to discover</span></div><div><strong>{saved.toString().padStart(2, "0")}</strong><span>sparks of interest</span></div></div>
      <div className="how-it-works"><span className="little-icon"><Icon name="sparkles" /></span><div><h2>A little curiosity goes a long way.</h2><p>Save what catches your eye. Your next favorite thing might be one swipe away.</p><Link href="/saved">See your saved finds <Icon name="arrow" size={16} /></Link></div></div>
      <p className="bookmark-note">Interested is a bookmark. Reach out to organizers separately to join or register.</p>
    </section>
  );
}
