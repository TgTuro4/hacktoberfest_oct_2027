import type { Metadata, Viewport } from "next";
import { Big_Shoulders, Instrument_Sans } from "next/font/google";
import { DemoProvider } from "@/components/demo-provider";
import { Shell } from "@/components/shell";
import "./globals.css";

const display = Big_Shoulders({ subsets: ["latin"], variable: "--font-display", adjustFontFallback: false });
const body = Instrument_Sans({ subsets: ["latin"], variable: "--font-body" });

export const metadata: Metadata = {
  title: "SocialShell · Everything at UMD",
  description: "Discover campus groups and events, one swipe at a time. A fictional UMD-themed student demo.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#ffffff" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className={`${display.variable} ${body.variable}`}><body><DemoProvider><Shell>{children}</Shell></DemoProvider></body></html>;
}
