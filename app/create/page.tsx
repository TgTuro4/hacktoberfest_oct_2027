"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useDemo } from "@/components/demo-provider";
import { Icon } from "@/components/icon";
import { ItemForm } from "@/components/item-form";
import { emptyDraft, type Draft, type ItemKind, type PrefillResult } from "@/lib/types";
import { MAX_ANNOUNCEMENT } from "@/lib/validation";
import { SAMPLE_ANNOUNCEMENT } from "@/lib/sample";

export default function CreatePage() {
  const { addItem } = useDemo();
  const [kind, setKind] = useState<ItemKind>("event");
  const [initial, setInitial] = useState<Draft>(emptyDraft());
  const [formVersion, setFormVersion] = useState(0);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PrefillResult | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [published, setPublished] = useState<number[]>([]);
  const [success, setSuccess] = useState("");
  const [image, setImage] = useState("");
  const [imageError, setImageError] = useState("");
  const request = useRef<AbortController | null>(null);
  const requestVersion = useRef(0);
  const formPanel = useRef<HTMLDivElement>(null);
  useEffect(() => () => { request.current?.abort(); }, []);
  useEffect(() => () => { if (image) URL.revokeObjectURL(image); }, [image]);

  function applyDraft(draft: Draft, index: number | null) {
    setKind(draft.kind); setInitial(draft); setSelected(index); setFormVersion(v => v + 1); setSuccess("");
  }
  function selectKind(value: ItemKind) {
    if (kind === value) return;
    applyDraft(emptyDraft(value), null);
  }
  function changeText(value: string) {
    requestVersion.current++;
    request.current?.abort(); setBusy(false); setText(value); setResult(null); setSelected(null); setPublished([]); setError("");
  }
  async function prefill() {
    if (!text.trim() || busy) return;
    const version = ++requestVersion.current;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true); setError(""); setSuccess("");
    try {
      const response = await fetch("/api/prefill", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }), signal: controller.signal });
      const data = await response.json();
      if (version !== requestVersion.current) return;
      if (!response.ok) throw new Error(data.error || "Prefill couldn’t finish. Try again or enter details manually.");
      const next = data as PrefillResult;
      setResult(next); setPublished([]); setSelected(null);
      if (next.drafts.length === 1) applyDraft(next.drafts[0], 0);
    } catch (err) {
      if (version === requestVersion.current && !controller.signal.aborted) setError(err instanceof Error ? err.message : "Prefill couldn’t finish. Try manual entry.");
    } finally { if (version === requestVersion.current) setBusy(false); }
  }
  function upload(event: ChangeEvent<HTMLInputElement>) {
    setImageError(""); setImage("");
    const file = event.target.files?.[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) { setImageError("Choose a JPEG, PNG, or WebP image."); event.target.value = ""; return; }
    if (file.size > 3 * 1024 * 1024) { setImageError("That image is too large. The limit is 3 MB."); event.target.value = ""; return; }
    setImage(URL.createObjectURL(file));
  }
  function publish(draft: Draft) {
    if (!addItem(draft)) return false;
    setSuccess(`“${draft.title.trim()}” is published! Find it in Discover.`);
    if (selected !== null) setPublished(list => [...list, selected]);
    setSelected(null); setInitial(emptyDraft(kind)); setFormVersion(v => v + 1);
    return true;
  }
  return <section>
    <div className="page-heading"><h1>Make room for connection.</h1><p>A study crew. A game night. A big idea. It starts with you.</p></div>
    {success && <div className="notice success" role="status"><Icon name="check" size={22} /><div>{success} <Link href="/discover" className="text-link">View in Discover</Link>{result && published.length < result.drafts.length && <p>Select another draft below to create it next.</p>}</div></div>}
    <div className="creation-layout">
      <aside className="creation-tools">
        <div className="panel ai-panel"><div className="ai-title"><span className="little-icon"><Icon name="sparkles" /></span><span className="step-label">A little head start</span></div><h2>From announcement<br />to almost ready.</h2><p>Paste a message to prefill your details, then give them a once-over.</p>
          <label className="announcement-label">Announcement<textarea aria-label="Announcement" value={text} onChange={e => changeText(e.target.value)} rows={7} maxLength={MAX_ANNOUNCEMENT} placeholder="Hey Terps! We’re hosting a game night at Stamp…" /><small>{text.length.toLocaleString()} / {MAX_ANNOUNCEMENT.toLocaleString()} characters</small></label>
          <button className="button dark full-width" onClick={prefill} disabled={busy || !text.trim()}><Icon name="sparkles" size={18} />{busy ? "Preparing your drafts…" : "Prefill with AI"}</button>
          <button className="sample-button" disabled={busy} onClick={() => changeText(SAMPLE_ANNOUNCEMENT)}>Load sample announcement <Icon name="arrow" size={16} /></button>
          <p className="ai-footnote">Snowflake Cortex powers configured text extraction. Without credentials, only this exact sample has a prewritten demo response. Prefill never publishes for you.</p>
          {error && <div className="notice error" role="alert">{error}</div>}
          {result && <div className="draft-results"><div className="notice subtle" role="status"><div><strong>{result.source === "sample" ? "Sample demo · Not an AI result" : "Snowflake AI · Review required"}</strong><p>{result.message}</p></div></div>{!result.drafts.length && <p>No groups or events found. Try a clearer announcement or enter details manually.</p>}{result.drafts.map((draft, index) => <button key={index} className={`draft-option ${selected === index ? "selected" : ""}`} disabled={published.includes(index)} onClick={() => { applyDraft(draft, index); if (window.innerWidth < 760) formPanel.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }}><span><small>{draft.kind} {published.includes(index) ? "· published" : "· draft"}</small><strong>{draft.title || "Untitled draft"}</strong></span><Icon name={published.includes(index) ? "check" : "arrow"} size={18} /></button>)}</div>}
        </div>
        <div className="panel flyer-panel"><h3>Have a flyer?</h3><p>Keep it handy while filling in the details.</p><label className="upload-area"><Icon name="upload" size={24} /><span>Choose a flyer image</span><small>JPEG, PNG, WebP · up to 3 MB</small><input type="file" accept="image/jpeg,image/png,image/webp" onChange={upload} aria-label="Upload event flyer" /></label>{image && <div className="flyer-preview"><img src={image} alt="Your uploaded flyer preview" onError={() => { setImage(""); setImageError("That file couldn’t be displayed as an image."); }} /><button className="text-button" onClick={() => setImage("")}>Remove preview</button></div>}{imageError && <p role="alert" className="field-error">{imageError}</p>}<p className="ai-footnote"><strong>Image AI extraction is unavailable.</strong> This preview stays on your device, isn’t uploaded, and isn’t attached to the published card. Enter flyer details manually.</p></div>
      </aside>
      <div className="panel manual-panel" ref={formPanel}><div className="kind-selector segmented" aria-label="Create type"><button aria-pressed={kind === "event"} className={kind === "event" ? "selected" : ""} onClick={() => selectKind("event")}>Create an event</button><button aria-pressed={kind === "group"} className={kind === "group" ? "selected" : ""} onClick={() => selectKind("group")}>Create a group</button></div>{selected !== null && result && <div className="review-notes"><strong>Please review this draft</strong><ul>{["Check every field against the original announcement.", ...result.drafts[selected].reviewNotes].map((note, index) => <li key={index}>{note}</li>)}</ul></div>}<ItemForm key={formVersion} initial={initial} onPublish={publish} /></div>
    </div>
  </section>;
}
