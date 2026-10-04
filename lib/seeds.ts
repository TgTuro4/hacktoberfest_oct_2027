import type { CampusItem, DemoState } from "./types";
import umdSeed from "./umd-seed.json";

const entries: Omit<CampusItem, "id" | "demo" | "color" | "createdAt">[] = [
  { kind: "group", title: "The Debug Club", description: "Big ideas. Small bugs. Find your people at our laid-back CS study sessions. Bring a tricky problem, a side project, or just your curiosity.", tags: ["Technology", "Study buddies", "Computer science"], location: "Brendan Iribe Center", meetingDetails: "Wednesdays · 5:00–7:00 PM", date: "", time: "" },
  { kind: "event", title: "One more round?", description: "A board game night with friendly rivals and zero experience required. From Catan to party games, there's a seat at the table for you.", tags: ["Board games", "Social", "Just for fun"], location: "Stamp Student Union", date: "2026-10-09", time: "19:00", meetingDetails: "" },
  { kind: "group", title: "Take the scenic route", description: "Trade your screen time for trail time. Join a beginner-friendly hiking crew for fresh air, good conversations, and weekend adventures.", tags: ["Outdoors", "Wellness", "Adventure"], location: "Meet at McKeldin Mall", meetingDetails: "Weekend hikes · plans shared at meetups", date: "", time: "" },
  { kind: "event", title: "Build something together", description: "Have a hackathon idea? Need a teammate? Come meet curious builders across majors and sketch out your next big thing.", tags: ["Hackathons", "Technology", "Design"], location: "Iribe Center lobby", date: "2026-10-16", time: "18:00", meetingDetails: "" },
  { kind: "group", title: "A little creative chaos", description: "An open sketchbook, a fresh playlist, and a room full of makers. A low-pressure space to draw, design, and try something new.", tags: ["Art", "Design", "Creative"], location: "The Clarice", meetingDetails: "Thursdays · 6:00 PM", date: "", time: "" },
  { kind: "event", title: "Coffee & connections", description: "Meet fellow Terps over a cup of something warm. Easy conversation prompts, new faces, and your next campus friend.", tags: ["Social", "Coffee", "Community"], location: "McKeldin Library café", date: "2026-10-12", time: "15:30", meetingDetails: "" },
  { kind: "group", title: "Good food, good company", description: "Cook something new and share it with friends. A student cooking circle for kitchen beginners and ambitious home chefs alike.", tags: ["Food", "Culture", "Community"], location: "South Campus Commons", meetingDetails: "Sundays · 4:00 PM", date: "", time: "" },
  { kind: "event", title: "Golden hour on the Mall", description: "Slow down with an easy outdoor yoga session. Bring a mat or towel and take a little breathing room before the week begins.", tags: ["Wellness", "Outdoors", "Fitness"], location: "McKeldin Mall", date: "2026-10-11", time: "17:00", meetingDetails: "" },
];

/** Set NEXT_PUBLIC_DEMO_DATA=umd (e.g. in .env.local) to demo with real scraped UMD events and student orgs. */
const useUmdData = process.env.NEXT_PUBLIC_DEMO_DATA === "umd";

export function freshDemo(): DemoState {
  return {
    version: 1,
    items: useUmdData ? (umdSeed as CampusItem[]).map(item => ({ ...item, tags: [...item.tags] })) : entries.map((entry, index) => ({ ...entry, tags: [...entry.tags], id: `demo-${index + 1}`, demo: true, color: index % 4, createdAt: "2026-10-01T12:00:00Z" })),
    decisions: {},
    profile: { name: "Alex Morgan", major: "Computer Science", bio: "Finding my people, one new thing at a time.", interests: ["Technology", "Outdoors", "Board games"], availability: "Weekday evenings & weekends" },
  };
}
