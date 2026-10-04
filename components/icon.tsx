import type { CSSProperties } from "react";

export type IconName = "home" | "discover" | "plus" | "bookmark" | "user" | "pin" | "clock" | "arrow" | "close" | "sparkles" | "upload" | "check" | "refresh" | "leaf" | "code";
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
};

export function Icon({ name, size = 22, style, className = "" }: { name: IconName; size?: number; style?: CSSProperties; className?: string }) {
  return <svg className={className} style={style} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name].map((d, i) => <path d={d} key={i} />)}</svg>;
}
