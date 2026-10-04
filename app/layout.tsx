import type { Metadata, Viewport } from "next";
import { DemoProvider } from "@/components/demo-provider";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "TerpLink · Find your people",
  description: "Discover campus groups and events, one swipe at a time. A fictional UMD-themed student demo.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#f8f6f1" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><DemoProvider><Shell>{children}</Shell></DemoProvider></body></html>;
}
