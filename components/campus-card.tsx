import type { CampusItem } from "@/lib/types";
import { Icon, type IconName } from "./icon";

function clockTime(time: string) {
  const [hour, minute] = time.split(":").map(Number);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return "";
  return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour >= 12 ? "PM" : "AM"}`;
}

export function schedule(item: CampusItem) {
  if (item.kind === "group") return item.meetingDetails || "Meeting details to come";
  const day = new Date(`${item.date}T12:00:00`);
  if (Number.isNaN(day.getTime())) return "Date to come";
  return `${day.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} · ${clockTime(item.time) || "Time to come"}`;
}

/** The glanceable version shown on the poster: "Fri, Oct 9 at 7:00 PM". */
export function shortSchedule(item: CampusItem) {
  if (item.kind === "group") return item.meetingDetails || "Meets regularly";
  const day = new Date(`${item.date}T12:00:00`);
  if (Number.isNaN(day.getTime())) return "Date to come";
  const date = day.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
  const time = clockTime(item.time);
  return time ? `${date} at ${time}` : date;
}

const glyphs: [RegExp, IconName][] = [
  [/board game|game night|catan/i, "dice"],
  [/coffee|café|cafe/i, "coffee"],
  [/food|cook|chef|culture/i, "food"],
  [/art|draw|creative|sketch/i, "palette"],
  [/hik|trail|adventure|scenic/i, "mountain"],
  [/yoga|fitness|wellness/i, "sun"],
  [/tech|computer|hack|code|cs\b/i, "code"],
];

export function glyphFor(item: CampusItem): IconName {
  const text = `${item.tags.join(" ")} ${item.title}`;
  return glyphs.find(([pattern]) => pattern.test(text))?.[1] ?? "sparkles";
}

function PosterArt({ item }: { item: CampusItem }) {
  return <div className="poster-art" aria-hidden="true">
    <div className="poster-bend" />
    <Icon name={glyphFor(item)} className="poster-glyph" size={240} strokeWidth={1.15} />
    {/* Flyers have text, so show the whole image over a blurred copy of itself. A broken link hides both and the art shows through. */}
    {item.image && <>
      <img className="poster-photo-bg" src={item.image} alt="" loading="lazy" draggable={false} referrerPolicy="no-referrer" onError={event => { event.currentTarget.style.display = "none"; }} />
      <img className="poster-photo" src={item.image} alt="" loading="lazy" draggable={false} referrerPolicy="no-referrer" onError={event => { event.currentTarget.style.display = "none"; }} />
    </>}
  </div>;
}

/** `onInfo` adds the little "i" button in the corner (used on the swipe deck to jump to the full details). */
export function CampusCard({ item, compact = false, onInfo }: { item: CampusItem; compact?: boolean; onInfo?: () => void }) {
  return <article className={`poster tone-${item.color % 4} ${compact ? "poster-compact" : ""} ${item.image ? "has-photo" : ""}`} aria-label={`${item.kind}: ${item.title}`}>
    <PosterArt item={item} />
    <div className="poster-top">
      <span className="poster-chip">{item.kind === "group" ? "Group" : "Event"}</span>
      {onInfo && <button className="poster-info-btn" aria-label={`More about ${item.title}`} onPointerDown={event => event.stopPropagation()} onClick={onInfo}><Icon name="info" size={20} strokeWidth={2.8} /></button>}
    </div>
    <div className="poster-info">
      <h2>{item.title}</h2>
      <p><Icon name="pin" size={16} /><span>{item.location || "Location to come"}</span></p>
      {!compact && <p><Icon name="clock" size={16} /><span>{shortSchedule(item)}</span></p>}
      {!compact && item.tags.length > 0 && <div className="poster-tags">{item.tags.slice(0, 3).map(tag => <span key={tag}>{tag}</span>)}</div>}
    </div>
  </article>;
}

/** Tiny title-only poster used for the sidebar picks grid. */
export function MiniPoster({ item }: { item: CampusItem }) {
  return <span className={`poster poster-mini tone-${item.color % 4}`}>
    <PosterArt item={item} />
    <span className="poster-mini-title">{item.title}</span>
  </span>;
}
