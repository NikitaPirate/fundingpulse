import type { Metadata, Viewport } from "next";
import Script from "next/script";

import { AppFrame } from "./_components/AppFrame";
import { ThemeProvider } from "./_theme/ThemeProvider";
import "./globals.css";

// This script must be inlined before hydration to avoid a theme flash.
const themeInitScript = `
(() => {
  const storageKey = "fundingpulse-theme";
  const root = document.documentElement;
  const storedTheme = window.localStorage.getItem(storageKey);
  const resolvedTheme =
    storedTheme === "light" || storedTheme === "dark"
      ? storedTheme
      : window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";

  root.dataset.theme = resolvedTheme;
})();
`.trim();

export const metadata: Metadata = {
  title: "FundingPulse",
  description: "Frontend shell for FundingPulse funding workflows.",
  icons: {
    icon: "/logo.svg",
    shortcut: "/logo.svg",
  },
};

export const viewport: Viewport = {
  themeColor: [
    {
      color: "#060b11",
      media: "(prefers-color-scheme: dark)",
    },
    {
      color: "#e7edf2",
      media: "(prefers-color-scheme: light)",
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Script id="theme-init" strategy="beforeInteractive">
          {themeInitScript}
        </Script>
        <a className="skipLink" href="#main-content">
          Skip to content
        </a>
        <ThemeProvider>
          <AppFrame>{children}</AppFrame>
        </ThemeProvider>
      </body>
    </html>
  );
}
