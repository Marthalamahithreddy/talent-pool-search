"use client";
// =============================================================
// FILE: frontend/components/CandidateCard.tsx
// PURPOSE: A compact card shown in the search results grid.
//          Displays name, title, location, experience, and skill chips.
//          Clicking anywhere on the card navigates to the detail page.
//
// Props:
//   candidate → CandidateCard type from types.ts
// =============================================================

import Link from "next/link";
import { MapPin, Briefcase } from "lucide-react";
import type { CandidateCard as CandidateCardType } from "@/lib/types";

interface Props {
  candidate: CandidateCardType;
}

// Only show this many skill chips per card to keep cards compact
const MAX_SKILLS_SHOWN = 5;

export default function CandidateCard({ candidate }: Props) {
  const visibleSkills = candidate.skills.slice(0, MAX_SKILLS_SHOWN);
  const hiddenCount = candidate.skills.length - visibleSkills.length;

  return (
    <Link href={`/candidates/${candidate.id}`} className="block group">
      <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm hover:shadow-md hover:border-brand-300 transition-all h-full flex flex-col gap-3">

        {/* Name + Title */}
        <div>
          <h3 className="font-semibold text-gray-900 group-hover:text-brand-600 transition-colors">
            {candidate.name || "Unknown Candidate"}
          </h3>
          {candidate.current_title && (
            <p className="text-sm text-gray-500 mt-0.5">{candidate.current_title}</p>
          )}
        </div>

        {/* Location + Experience */}
        <div className="flex flex-wrap gap-3 text-xs text-gray-500">
          {candidate.location && (
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              {candidate.location}
            </span>
          )}
          {candidate.years_experience != null && (
            <span className="flex items-center gap-1">
              <Briefcase className="w-3 h-3" />
              {candidate.years_experience} yr{candidate.years_experience !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {/* Skill chips */}
        {visibleSkills.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-auto">
            {visibleSkills.map((skill) => (
              <span
                key={skill}
                className="px-2 py-0.5 rounded-full bg-brand-50 text-brand-700 text-xs font-medium"
              >
                {skill}
              </span>
            ))}
            {hiddenCount > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 text-xs">
                +{hiddenCount} more
              </span>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}
