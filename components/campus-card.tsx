import type { CampusItem } from "@/lib/types";
import { Icon } from "./icon";

export function schedule(item: CampusItem) {
  if (item.kind === "group") return item.meetingDetails || "Meeting details to come";
  const day = new Date(`${item.date}T12:00:00`);
  if (Number.isNaN(day.getTime())) return "Date to come";
  const [hour, minute] = item.time.split(":").map(Number);
  const time = Number.isFinite(hour) && Number.isFinite(minute) ? `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour >= 12 ? "PM" : "AM"}` : "Time to come";
  return `${day.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} · ${time}`;
}

export function CampusCard({ item, compact = false }: { item: CampusItem; compact?: boolean }) {
  const artIcon = item.tags.some(t => /outdoor|wellness/i.test(t)) ? "leaf" : item.tags.some(t => /tech|computer|hack/i.test(t)) ? "code" : "sparkles";
  return <article className={`campus-card color-${item.color % 4} ${compact ? "compact-card" : ""}`} aria-label={`${item.kind}: ${item.title}`}>
    <div className="card-art">
      <div className="art-grid" /><div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
      <span className="art-spark spark-one" aria-hidden="true">✳</span><span className="art-spark spark-two" aria-hidden="true">✦</span>
      <div className="art-center"><Icon name={artIcon} size={58} /></div>
      <span className="art-note" aria-hidden="true">{item.kind === "group" ? "your kind of people" : "make a little time"}</span>
      <span className="kind-label">{item.kind === "group" ? "Campus group" : "Campus event"}</span>
      {item.demo && <span className="demo-badge">DEMO DATA</span>}
    </div>
    <div className="card-body">
      <h2>{item.title}</h2><p className="card-description">{item.description}</p>
      <div className="tags">{item.tags.map(tag => <span key={tag}>{tag}</span>)}</div>
      <div className="card-details"><p><Icon name="pin" size={18} /><span>{item.location || "Location to come"}</span></p><p><Icon name="clock" size={18} /><span>{schedule(item)}{item.kind === "event" && <small>Campus time · America/New_York</small>}</span></p></div>
    </div>
  </article>;
}
