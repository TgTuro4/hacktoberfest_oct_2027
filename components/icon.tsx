import type { CSSProperties } from "react";

export type IconName = "home" | "discover" | "plus" | "bookmark" | "user" | "pin" | "clock" | "arrow" | "close" | "sparkles" | "upload" | "check" | "refresh" | "leaf" | "code" | "heart" | "info" | "undo" | "dice" | "coffee" | "food" | "palette" | "sun" | "mountain";
const paths: Record<IconName, string[]> = {
  home: ["m3 10 9-7 9 7", "M5 9v12h14V9", "M9 21v-8h6v8"],
  discover: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z", "m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z"],
  plus: ["M12 5v14M5 12h14"],
  bookmark: ["M6 4h12v17l-6-4-6 4V4Z"],
  user: ["M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z", "M4 21v-2a8 8 0 0 1 16 0v2"],
  pin: ["M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z", "M14 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z"],
  clock: ["M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z", "M12 7v5l3 2"],
  arrow: ["M5 12h14m-5-5 5 5-5 5"],
  close: ["m6 6 12 12M6 18 18 6"],
  sparkles: ["m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z", "M21 2v4m-2-2h4"],
  upload: ["M12 16V3m-5 5 5-5 5 5", "M4 15v6h16v-6"],
  check: ["m5 12 4 4L19 6"],
  refresh: ["M20 7v5h-5", "M20 12a8 8 0 1 0-2 5", "M20 7 18 5"],
  leaf: ["M20 3C8 3 3 8 5 15s15 8 15-12Z", "M4 21 16 9"],
  code: ["m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16"],
  heart: ["M12 20s-7.5-4.6-9.4-9.3A5.2 5.2 0 0 1 12 6.1a5.2 5.2 0 0 1 9.4 4.6C19.5 15.4 12 20 12 20Z"],
  info: ["M12 10.5v7", "M12 6.5v.01"],
  undo: ["M9 14 4 9l5-5", "M4 9h10.5a5.5 5.5 0 0 1 0 11H11"],
  dice: ["M6 3h12a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3Z", "M8.5 8.5h.01M15.5 8.5h.01M12 12h.01M8.5 15.5h.01M15.5 15.5h.01"],
  coffee: ["M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V9Z", "M17 11h1.5a2.5 2.5 0 0 1 0 5H17", "M8 3v3M12 3v3"],
  food: ["M7 3v18", "M4 3v5a3 3 0 0 0 6 0V3", "M17 21V3c-2.5 1-4 4-4 8h4"],
  palette: ["M12 3a9 9 0 1 0 0 18c1.1 0 2-.9 2-2 0-.5-.2-1-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1.1.9-2 2-2h2.3A4.7 4.7 0 0 0 21 9.8C21 6 17 3 12 3Z", "M7.5 11.5h.01M9.5 7.5h.01M14.5 7.5h.01"],
  sun: ["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z", "M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"],
  mountain: ["m2 20 7-12 4.5 7.5L16 12l6 8H2Z", "m7.2 11 1.8 1.5 1.6-1.3"],
};

export function Icon({ name, size = 22, style, className = "", strokeWidth = 1.7 }: { name: IconName; size?: number; style?: CSSProperties; className?: string; strokeWidth?: number }) {
  return <svg className={className} style={style} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {paths[name].map((d, i) => <path d={d} key={i} />)}
  </svg>;
}
