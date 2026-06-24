"use client";
// =============================================================
// FILE: frontend/app/candidates/[id]/page.tsx
// PURPOSE: Page 3 — Full candidate profile.
//          Shows all extracted data:
//            - Contact details (regex-extracted)
//            - AI-extracted professional info
//            - All skill chips
//            - Link to download original resume from S3
// =============================================================

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Mail, Phone, Linkedin, MapPin,
  Briefcase, Download, Loader2
} from "lucide-react";
import { getCandidate } from "@/lib/api";
import type { CandidateDetail } from "@/lib/types";

export default function CandidateDetailPage() {
  const params   = useParams();
  const router   = useRouter();
  const id       = params.id as string;

  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);

  useEffect(() => {
    getCandidate(id)
      .then(setCandidate)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load profile."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32 gap-2 text-gray-400">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span className="text-sm">Loading profile…</span>
      </div>
    );
  }

  if (error || !candidate) {
    return (
      <div className="max-w-xl mx-auto space-y-4 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error || "Candidate not found."}
        </div>
        <button onClick={() => router.back()} className="text-sm text-brand-600 underline">
          ← Back to search
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back link */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-brand-600 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to search
      </button>

      {/* Header card */}
      <div className="bg-white border border-gray-100 rounded-xl p-6 shadow-sm space-y-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            {candidate.name || "Unknown Candidate"}
          </h1>
          {candidate.current_title && (
            <p className="text-gray-500 text-sm mt-0.5">{candidate.current_title}</p>
          )}
        </div>

        {/* Location + Experience */}
        <div className="flex flex-wrap gap-4 text-sm text-gray-600">
          {candidate.location && (
            <span className="flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-brand-500" />
              {candidate.location}
            </span>
          )}
          {candidate.years_experience != null && (
            <span className="flex items-center gap-1.5">
              <Briefcase className="w-4 h-4 text-brand-500" />
              {candidate.years_experience} years experience
            </span>
          )}
        </div>

        {/* Contact details */}
        <div className="border-t border-gray-100 pt-4 space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400">Contact</h2>
          <div className="space-y-1.5 text-sm">
            {candidate.email && (
              <a href={`mailto:${candidate.email}`} className="flex items-center gap-2 text-brand-600 hover:underline">
                <Mail className="w-4 h-4" />
                {candidate.email}
              </a>
            )}
            {candidate.phone && (
              <span className="flex items-center gap-2 text-gray-700">
                <Phone className="w-4 h-4 text-gray-400" />
                {candidate.phone}
              </span>
            )}
            {candidate.linkedin_url && (
              <a
                href={candidate.linkedin_url.startsWith("http") ? candidate.linkedin_url : `https://${candidate.linkedin_url}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-brand-600 hover:underline"
              >
                <Linkedin className="w-4 h-4" />
                LinkedIn Profile
              </a>
            )}
            {!candidate.email && !candidate.phone && !candidate.linkedin_url && (
              <p className="text-gray-400 text-xs">No contact details extracted.</p>
            )}
          </div>
        </div>
      </div>

      {/* Skills */}
      {candidate.skills.length > 0 && (
        <div className="bg-white border border-gray-100 rounded-xl p-6 shadow-sm space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400">Skills</h2>
          <div className="flex flex-wrap gap-2">
            {candidate.skills.map((skill) => (
              <span
                key={skill}
                className="px-3 py-1 rounded-full bg-brand-50 text-brand-700 text-sm font-medium"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Download resume */}
      {candidate.s3_url && (
        <a
          href={candidate.s3_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 w-full py-3 rounded-xl border border-brand-300 text-brand-600 font-medium text-sm hover:bg-brand-50 transition-colors"
        >
          <Download className="w-4 h-4" />
          Download Original Resume
        </a>
      )}
    </div>
  );
}
