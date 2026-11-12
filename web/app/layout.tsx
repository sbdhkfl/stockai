import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FAIRVALUE AI",
  description:
    "Transparent, model-independent stock valuation. Estimates only — not investment advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, background: "#f7f8fa" }}>
        <header style={{ background: "#111827", color: "#fff", padding: "12px 24px",
          display: "flex", alignItems: "center", gap: 16 }}>
          <a href="/" style={{ color: "#fff", fontWeight: 700, textDecoration: "none", fontSize: 18 }}>
            FAIRVALUE AI
          </a>
          <span style={{ color: "#9ca3af", fontSize: 13 }}>
            Estimates conditional on stated assumptions — not investment advice
          </span>
        </header>
        <main style={{ maxWidth: 1080, margin: "0 auto", padding: 24 }}>{children}</main>
      </body>
    </html>
  );
}
