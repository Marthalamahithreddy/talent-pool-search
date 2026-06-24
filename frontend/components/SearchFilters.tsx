"use client";
// =============================================================
// FILE: frontend/components/SearchFilters.tsx
// PURPOSE: Filter bar at the top of the candidate search page.
//          Three filters: skill keyword, location, minimum experience.
//          Changes are debounced 400ms before calling onSearch to
//          avoid firing a backend call on every keystroke.
//
// Props:
//   onSearch(params) → called with updated search params after debounce
// =============================================================

import { useState, useEffect, useRef } from "react";
import { Search, MapPin, Briefcase, X } from "lucide-react";
import type { SearchParams } from "@/lib/types";
import { suggestSkills } from "@/lib/api";

interface Props {
  onSearch: (params: SearchParams) => void;
}

export default function SearchFilters({ onSearch }: Props) {
  const [skill, setSkill]       = useState("");
  const [location, setLocation] = useState("");
  const [minExp, setMinExp]     = useState("");

  // Skill autocomplete state
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce: fire onSearch 400ms after the last change
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      onSearch({
        skill:    skill.trim() || undefined,
        location: location.trim() || undefined,
        min_exp:  minExp !== "" ? parseFloat(minExp) : undefined,
      });
    }, 400);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [skill, location, minExp, onSearch]);

  // Fetch skill suggestions as the user types (debounced 250ms)
  const suggestRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (suggestRef.current) clearTimeout(suggestRef.current);
    if (!skill.trim()) {
      setSuggestions([]);
      return;
    }
    suggestRef.current = setTimeout(async () => {
      const results = await suggestSkills(skill.trim());
      // Hide the dropdown if the only suggestion exactly matches the input
      setSuggestions(results.filter((s) => s.toLowerCase() !== skill.trim().toLowerCase()));
    }, 250);

    return () => {
      if (suggestRef.current) clearTimeout(suggestRef.current);
    };
  }, [skill]);

  function pickSuggestion(value: string) {
    setSkill(value);
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function clearAll() {
    setSkill("");
    setLocation("");
    setMinExp("");
    setSuggestions([]);
  }

  const hasFilters = skill || location || minExp;

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Skill filter with autocomplete */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={skill}
            onChange={(e) => { setSkill(e.target.value); setShowSuggestions(true); }}
            onFocus={() => setShowSuggestions(true)}
            // Delay so a click on a suggestion registers before the list hides
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="Skill (e.g. Python, React)"
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
          />

          {/* Suggestions dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <ul className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-56 overflow-auto">
              {suggestions.map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}  // keep input focus
                    onClick={() => pickSuggestion(s)}
                    className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-brand-50 hover:text-brand-700"
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Location filter */}
        <div className="relative">
          <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Location (e.g. London, NYC)"
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
          />
        </div>

        {/* Min experience filter */}
        <div className="relative">
          <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="number"
            min={0}
            max={40}
            step={0.5}
            value={minExp}
            onChange={(e) => setMinExp(e.target.value)}
            placeholder="Min years experience"
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
          />
        </div>
      </div>

      {hasFilters && (
        <button
          onClick={clearAll}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-red-500 transition-colors"
        >
          <X className="w-3 h-3" />
          Clear all filters
        </button>
      )}
    </div>
  );
}
