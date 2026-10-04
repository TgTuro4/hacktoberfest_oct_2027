"use client";

import { useState, type FormEvent } from "react";
import type { Draft } from "@/lib/types";
import { draftErrors, parseTags } from "@/lib/validation";
import { Icon } from "./icon";

export function ItemForm({ initial, onPublish }: { initial: Draft; onPublish: (draft: Draft) => boolean }) {
  const [draft, setDraft] = useState(initial);
  const [tags, setTags] = useState(initial.tags.join(", "));
  const [errors, setErrors] = useState<string[]>([]);
  function field(key: keyof Omit<Draft, "tags" | "kind">, value: string) { setDraft({ ...draft, [key]: value }); setErrors([]); }
  function submit(event: FormEvent) {
    event.preventDefault();
    const result = { ...draft, tags: parseTags(tags) };
    const problems = draftErrors(result);
    setErrors(problems);
    if (!problems.length) onPublish(result);
  }
  return <form onSubmit={submit} className="item-form">
    <div className="panel-heading"><span className="step-label">Review and make it yours</span><h2>{draft.kind === "event" ? "The event details" : "The group details"}</h2><p>Give people a reason to say “I’m in.”</p></div>
    {errors.length > 0 && <div role="alert" className="notice error">{errors.map(error => <p key={error}>{error}</p>)}</div>}
    <label>{draft.kind === "event" ? "Event title" : "Group name"} <span>*</span><input aria-label={draft.kind === "event" ? "Event title" : "Group name"} value={draft.title} onChange={e => field("title", e.target.value)} required maxLength={100} placeholder={draft.kind === "event" ? "Something worth showing up for" : "A name for your people"} /></label>
    <label>Description {draft.kind === "group" && <span>*</span>}<textarea aria-label="Description" rows={4} value={draft.description} onChange={e => field("description", e.target.value)} required={draft.kind === "group"} maxLength={2000} placeholder="What’s the vibe? Who’s it for? Tell us a little more." /></label>
    <label>Interest tags<input aria-label="Interest tags" value={tags} onChange={e => setTags(e.target.value)} maxLength={260} placeholder="Technology, outdoors, board games" /><small>Separate with commas. Up to 8 tags, 30 characters each.</small></label>
    <label>Location {draft.kind === "event" ? <span>*</span> : <span className="optional">optional</span>}<input aria-label="Location" value={draft.location} onChange={e => field("location", e.target.value)} required={draft.kind === "event"} maxLength={200} placeholder="A place on (or around) campus" /></label>
    {draft.kind === "event" ? <><div className="form-row"><label>Date <span>*</span><input aria-label="Date" type="date" value={draft.date} onChange={e => field("date", e.target.value)} required /></label><label>Time <span>*</span><input aria-label="Time" type="time" value={draft.time} onChange={e => field("time", e.target.value)} required /></label></div><p className="field-note">All event times are campus time (America/New_York).</p></> : <label>Recurring meeting details <span className="optional">optional</span><input aria-label="Recurring meeting details" value={draft.meetingDetails} onChange={e => field("meetingDetails", e.target.value)} maxLength={300} placeholder="Wednesdays at 5 PM, weekly study sessions…" /></label>}
    <div className="publish-note"><Icon name="check" size={18} /><p>Review your details before publishing. Your card will appear in this browser’s discovery feed.</p></div>
    <button type="submit" className="button primary full-width">Publish {draft.kind} <Icon name="arrow" size={20} /></button>
  </form>;
}
