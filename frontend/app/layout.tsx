// =============================================================
// FILE: frontend/app/layout.tsx
// PURPOSE: Root layout for the entire app.
//          Sets <html> lang, global font, and the persistent top nav.
//          All pages are rendered inside the <main> wrapper here.
// =============================================================

import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Talent Pool Search",
  description: "Upload resumes and search candidates by skill, location, and experience.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* Top navigation bar */}
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6 shadow-sm">
          <Link href="/" className="text-lg font-bold text-brand-600 tracking-tight">
            TalentPool
          </Link>
          <Link
            href="/"
            className="text-sm text-gray-600 hover:text-brand-600 transition-colors"
          >
            Upload
          </Link>
          <Link
            href="/candidates"
            className="text-sm text-gray-600 hover:text-brand-600 transition-colors"
          >
            Search Candidates
          </Link>
        </nav>

        <main className="max-w-6xl mx-auto px-4 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
