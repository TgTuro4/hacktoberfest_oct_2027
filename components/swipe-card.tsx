"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import type { CampusItem, Decision } from "@/lib/types";
import { CampusCard } from "./campus-card";
import { Icon } from "./icon";

const THRESHOLD = 90;

export function SwipeCard({ item, onDecision }: { item: CampusItem; onDecision: (decision: Decision) => Promise<boolean> }) {
  const [offset, setOffset] = useState(0);
  const [exiting, setExiting] = useState(false);
  const busy = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const gesture = useRef<{ id: number; x: number; y: number; offset: number; axis: "pending" | "horizontal" | "vertical" } | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  function decide(decision: Decision) {
    if (busy.current) return;
    busy.current = true;
    setExiting(true);
    setOffset(decision === "interested" ? 500 : -500);
    timer.current = setTimeout(async () => {
      if (!await onDecision(decision)) {
        busy.current = false;
        setExiting(false);
        setOffset(0);
      }
    }, window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 180);
  }

  function down(event: PointerEvent<HTMLDivElement>) {
    if (!event.isPrimary || event.button !== 0 || busy.current) return;
    gesture.current = { id: event.pointerId, x: event.clientX, y: event.clientY, offset: 0, axis: "pending" };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    const g = gesture.current;
    if (!g || g.id !== event.pointerId) return;
    const dx = event.clientX - g.x;
    const dy = event.clientY - g.y;
    if (g.axis === "pending" && Math.max(Math.abs(dx), Math.abs(dy)) > 10) {
      g.axis = Math.abs(dx) > Math.abs(dy) * 1.2 ? "horizontal" : "vertical";
    }
    if (g.axis === "horizontal") {
      g.offset = dx;
      setOffset(dx);
    }
  }
  function finish(event: PointerEvent<HTMLDivElement>, cancelled = false) {
    const g = gesture.current;
    if (!g || g.id !== event.pointerId) return;
    gesture.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (!cancelled && g.axis === "horizontal" && Math.abs(g.offset) >= THRESHOLD) decide(g.offset > 0 ? "interested" : "pass");
    else setOffset(0);
  }
  return <>
    <div className="card-stack"><div className="stack-underlay" />
      <div className={`swipe-surface ${exiting ? "exiting" : ""}`} data-testid="swipe-card" onPointerDown={down} onPointerMove={move} onPointerUp={event => finish(event)} onPointerCancel={event => finish(event, true)} onLostPointerCapture={() => { if (gesture.current) { gesture.current = null; setOffset(0); } }} style={{ transform: `translateX(${offset}px) rotate(${offset / 30}deg)`, transition: exiting || offset === 0 ? "transform 180ms ease" : "none" }}>
        <CampusCard item={item} />
        {Math.abs(offset) > 25 && <div aria-hidden="true" className={`swipe-stamp ${offset > 0 ? "stamp-save" : "stamp-pass"}`}>{offset > 0 ? "INTERESTED" : "PASS"}</div>}
      </div>
    </div>
    <div className="swipe-actions"><button disabled={exiting} className="pass-button" onClick={() => decide("pass")}><Icon name="close" /><span>Pass</span></button><button disabled={exiting} className="interested-button" onClick={() => decide("interested")}><Icon name="bookmark" /><span>Interested</span></button></div>
    <p className="gesture-hint">Swipe left to pass <span>·</span> right to save</p>
  </>;
}
