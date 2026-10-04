"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useDemo } from "./demo-provider";
import { Icon, type IconName } from "./icon";
import { MiniPoster } from "./campus-card";

const links: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/discover", label: "Discover", icon: "discover" },
  { href: "/create", label: "Create", icon: "plus" },
  { href: "/saved", label: "Saved", icon: "bookmark" },
  { href: "/profile", label: "Profile", icon: "user" },
];

function Brand() {
  return <Link href="/" className="brand" aria-label="SocialShell home"><span className="brand-mark" aria-hidden="true" />SocialShell</Link>;
}

function NavLinks({ pathname }: { pathname: string }) {
  return <>{links.map(link => <Link key={link.href} href={link.href} aria-current={pathname === link.href ? "page" : undefined} className={`nav-link ${pathname === link.href ? "active" : ""}`}><Icon name={link.icon} /><span>{link.label}</span></Link>)}</>;
}

function ResetDialog({ open, onCancel, onConfirm }: { open: boolean; onCancel: () => void; onConfirm: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);
  return <dialog ref={dialog} className="confirm-dialog" aria-labelledby="reset-title" onCancel={event => { event.preventDefault(); onCancel(); }} onClick={event => { if (event.target === dialog.current) onCancel(); }}>
    <h2 id="reset-title">Reset SocialShell?</h2>
    <p>This removes your created cards, profile edits and swipes in this browser, and brings the demo cards back. Nothing else in your browser is touched.</p>
    <div className="confirm-actions">
      <button className="button secondary" onClick={onCancel} autoFocus>Cancel</button>
      <button className="button primary" onClick={onConfirm}>Reset demo</button>
    </div>
  </dialog>;
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { state, ready, error, reset, resetVersion } = useDemo();
  const name = state?.profile.name.trim() || "Alex Morgan";
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map(n => n[0]).join("");
  const saved = state ? state.items.filter(item => state.decisions[item.id] === "interested") : [];
  const [confirmingReset, setConfirmingReset] = useState(false);
  function resetDemo() {
    reset();
    setConfirmingReset(false);
  }
  return <>
    <a href="#main" className="skip-link">Skip to content</a>
    <div className="app-frame">
      <aside className="sidebar">
        <div className="sidebar-head">
          <Brand />
          <Link href="/profile" className="sidebar-profile" aria-label="Edit your profile"><span className="avatar">{initials}</span><span>{name.split(/\s+/)[0]}</span></Link>
        </div>
        <div className="calvert-rule" aria-hidden="true" />
        <nav className="side-nav" aria-label="Main navigation"><NavLinks pathname={pathname} /></nav>
        <section className="picks" aria-labelledby="picks-heading">
          <h2 id="picks-heading">Saved <span>{saved.length}</span></h2>
          {saved.length
            ? <ul className="picks-grid">{saved.slice(0, 9).map(item => <li key={item.id}><Link href="/saved" aria-label={`${item.title} (open Saved)`}><MiniPoster item={item} /></Link></li>)}</ul>
            : <p className="picks-empty">Swipe right on something and it lands here.</p>}
        </section>
        <div className="sidebar-foot">
          <button onClick={() => setConfirmingReset(true)} className="text-button">Reset demo</button>
        </div>
      </aside>

      <header className="mobile-header">
        <Brand />
        <div className="header-right">
          <button onClick={() => setConfirmingReset(true)} className="text-button">Reset demo</button>
          <Link href="/profile" className="avatar" aria-label="Edit your profile">{initials}</Link>
        </div>
      </header>

      <main id="main" className={`main-content ${pathname === "/discover" ? "discovery-main" : ""} ${pathname === "/" ? "home-main" : ""}`}>
        {error && <div className="notice error" role="alert">{error}</div>}
        {!ready ? <div className="loading-state" role="status"><div className="loading-dot" />Getting your campus ready…</div> : state ? <div key={resetVersion}>{children}</div> : <div className="empty-state"><h1>Let’s start fresh.</h1><p>Use Reset demo to reopen your local data.</p></div>}
      </main>
    </div>
    <ResetDialog open={confirmingReset} onCancel={() => setConfirmingReset(false)} onConfirm={resetDemo} />
    <nav className="bottom-nav" aria-label="Main navigation"><div className="nav-inner"><NavLinks pathname={pathname} /></div></nav>
  </>;
}
