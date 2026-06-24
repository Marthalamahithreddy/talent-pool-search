"use client";
// =============================================================
// FILE: frontend/app/candidates/page.tsx
// PURPOSE: Page 2 — Search & Filter candidates.
//          Shows a stats bar (total count, avg experience),
//          filter inputs (skill / location / min experience),
//          and a responsive card grid of all matching candidates.
//          Fetches from GET /candidates with query params.
// =============================================================

import { useState, useCallback, useEffect } from "react";
import { Loader2, Users, MapPin, Tags, Briefcase } from "lucide-react";
import SearchFilters from "@/components/SearchFilters";
import CandidateCard from "@/components/CandidateCard";
import { searchCandidates, getStats } from "@/lib/api";
import type { CandidateCard as CandidateCardType, SearchParams, StatsResponse } from "@/lib/types";

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<CandidateCardType[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load all candidates + global stats on mount (no filters)
  useEffect(() => {
    fetchCandidates({});
    getStats().then(setStats).catch(() => setStats(null));
  }, []);

  const fetchCandidates = useCallback(async (params: SearchParams) => {
    setLoading(true);
    setError(null);
    try {
      const data = await searchCandidates(params);
      setCandidates(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load candidates.");
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Search Candidates</h1>
        <p className="mt-1 text-sm text-gray-500">
          Filter by skill, location, or years of experience to find the right person.
        </p>
      </div>

      {/* Global stats banner (whole pool, independent of filters) */}
      {stats && stats.total_candidates > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard icon={<Users className="w-4 h-4" />} label="Candidates" value={stats.total_candidates} />
          <StatCard icon={<MapPin className="w-4 h-4" />} label="Locations" value={stats.total_locations} />
          <StatCard icon={<Tags className="w-4 h-4" />} label="Skills" value={stats.total_skills} />
          <StatCard
            icon={<Briefcase className="w-4 h-4" />}
            label="Avg Experience"
            value={stats.avg_experience != null ? `${stats.avg_experience} yrs` : "—"}
          />
        </div>
      )}

      {/* Filters */}
      <SearchFilters onSearch={fetchCandidates} />

      {/* Result count for the current filter */}
      {!loading && !error && (
        <p className="text-sm text-gray-500">
          Showing <strong>{candidates.length}</strong> result{candidates.length !== 1 ? "s" : ""}
        </p>
      )}

      {/* Results */}
      {loading ? (
        <div className="flex items-center justify-center py-24 gap-2 text-gray-400">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading candidates…</span>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : candidates.length === 0 ? (
        <div className="text-center py-24 text-gray-400 text-sm">
          No candidates found.{" "}
          <a href="/" className="text-brand-600 underline">Upload some resumes</a> to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {candidates.map((c) => (
            <CandidateCard key={c.id} candidate={c} />
          ))}
        </div>
      )}
    </div>
  );
}

// Small stat tile used in the dashboard banner
function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl px-4 py-3 shadow-sm">
      <div className="flex items-center gap-1.5 text-brand-500">{icon}</div>
      <div className="mt-1 text-xl font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
