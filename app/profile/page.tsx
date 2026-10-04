"use client";

import { useState, type FormEvent } from "react";
import { useDemo } from "@/components/demo-provider";
import { Icon } from "@/components/icon";
import { parseTags } from "@/lib/validation";
import type { Profile } from "@/lib/types";

function ProfileForm({ initial }: { initial: Profile }) {
  const { saveProfile, mode, pending } = useDemo();
  const [profile, setProfile] = useState(initial);
  const [tags, setTags] = useState(initial.interests.join(", "));
  const [message, setMessage] = useState("");
  const initials = profile.name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(n => n[0]).join("") || "T";
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!profile.name.trim()) { setMessage("Add a display name first."); return; }
    if (await saveProfile({ ...profile, name: profile.name.trim(), interests: parseTags(tags) })) setMessage(mode === "snowflake" ? "Profile saved to Snowflake. You’re all set!" : "Profile saved in this browser. You’re all set!");
  }
  const field = (key: keyof Omit<Profile, "interests">, value: string) => { setProfile({ ...profile, [key]: value }); setMessage(""); };
  return <div className="profile-layout"><aside className="profile-summary"><div className="profile-avatar">{initials}</div><h2>{profile.name || "Your name here"}</h2><p>{profile.major || "Curiosity is a good major."}</p><p className="data-badge">{mode === "snowflake" ? "Shared campus catalog · private guest profile" : "Demo data, saved in this browser"}</p><div className="intro-rule" /><p className="profile-note">This is your one editable demo profile. Make it feel like you.</p></aside><form className="panel profile-form" onSubmit={submit}><div className="panel-heading"><h2>A little about you</h2><p>Start with the basics. Let your interests do the rest.</p></div><label>Display name <span>*</span><input name="name" value={profile.name} onChange={e => field("name", e.target.value)} required maxLength={80} autoComplete="nickname" /></label><label>Major<input value={profile.major} onChange={e => field("major", e.target.value)} maxLength={100} placeholder="What are you studying?" /></label><label>Short bio<textarea value={profile.bio} onChange={e => field("bio", e.target.value)} maxLength={400} rows={3} placeholder="A few words about you…" /></label><label>Interest tags<input value={tags} onChange={e => { setTags(e.target.value); setMessage(""); }} maxLength={260} placeholder="Technology, music, outdoors" /><small>Separate with commas. Up to 8 tags, 30 characters each.</small></label><label>Availability <span className="optional">optional</span><input value={profile.availability} onChange={e => field("availability", e.target.value)} maxLength={200} placeholder="Weekday evenings, Sunday afternoons…" /></label><button className="button primary full-width" type="submit" disabled={pending}>Save profile <Icon name="check" size={20} /></button><p role="status" className="status-message success">{message}</p></form></div>;
}

export default function ProfilePage() {
  const { state } = useDemo();
  if (!state) return null;
  return <section><h1 className="sr-only">Profile</h1><ProfileForm initial={state.profile} /></section>;
}
