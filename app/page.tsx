"use client";

import Link from "next/link";
import { useDemo } from "@/components/demo-provider";
import { CampusCard } from "@/components/campus-card";
import { Icon } from "@/components/icon";
import { Typewriter } from "@/components/typewriter";

export default function HomePage() {
  const { state } = useDemo();
  if (!state) return null;
  const available = state.items.filter(item => !state.decisions[item.id]);
  const saved = Object.values(state.decisions).filter(d => d === "interested").length;
  const fan = (available.length >= 3 ? available : state.items).slice(0, 3);
  return (
    <section className="home-intro">
      <div className="home-hero">
        <div className="home-fan" aria-hidden="true">
          {fan.map((item, index) => <div key={item.id} className={`fan-card fan-${index}`}><CampusCard item={item} compact /></div>)}
        </div>
        <div className="home-copy">
          <h1 aria-label="Everything at UMD"><Typewriter /><span className="type-rest" aria-hidden="true">at UMD</span></h1>
          <p className="intro-copy">Personalized for you. Swipe right on what sounds fun, left on what doesn’t.</p>
          <Link href="/discover" className="button primary home-discover-link">
            Start discovering
          </Link>
        </div>
      </div>
      <div className="discovery-stats">
        <div><strong>{available.length.toString().padStart(2, "0")}</strong><span>left to discover</span></div>
        <div><strong>{saved.toString().padStart(2, "0")}</strong><span>sparks of interest</span></div>
      </div>
      <div className="how-it-works">
        <span className="little-icon"><Icon name="sparkles" /></span>
        <div>
          <h2>A little curiosity goes a long way.</h2>
          <p>Everything you swipe right on waits in Saved, so you can decide later.</p>
          <Link href="/saved">See your saved finds <Icon name="arrow" size={16} /></Link>
        </div>
      </div>
    </section>
  );
}
