// =============================================================
// FILE: frontend/lib/api.ts
// PURPOSE: All HTTP calls to the FastAPI backend in one place.
//          No business logic here — just fetch wrappers.
//
// Functions:
//   uploadResumes(files)      → POST /upload → UploadJobResponse
//   getJobStatus(jobId)       → GET /jobs/{id} → JobStatusResponse
//   searchCandidates(params)  → GET /candidates → CandidateCard[]
//   getCandidate(id)          → GET /candidates/{id} → CandidateDetail
// =============================================================

import type {
  UploadJobResponse,
  JobStatusResponse,
  CandidateCard,
  CandidateDetail,
  SearchParams,
  StatsResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---- Upload --------------------------------------------------

export async function uploadResumes(files: File[]): Promise<UploadJobResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return res.json();
}

// ---- Job polling ---------------------------------------------

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);

  if (!res.ok) {
    throw new Error(`Failed to fetch job status for ${jobId}`);
  }

  return res.json();
}

// ---- Candidates search + detail -----------------------------

export async function searchCandidates(params: SearchParams): Promise<CandidateCard[]> {
  const url = new URL(`${API_BASE}/candidates`);

  if (params.skill)     url.searchParams.set("skill",    params.skill);
  if (params.location)  url.searchParams.set("location", params.location);
  if (params.min_exp !== undefined) {
    url.searchParams.set("min_exp", String(params.min_exp));
  }

  const res = await fetch(url.toString());

  if (!res.ok) {
    throw new Error("Failed to fetch candidates");
  }

  return res.json();
}

export async function getCandidate(id: string): Promise<CandidateDetail> {
  const res = await fetch(`${API_BASE}/candidates/${id}`);

  if (!res.ok) {
    if (res.status === 404) throw new Error("Candidate not found");
    throw new Error("Failed to fetch candidate profile");
  }

  return res.json();
}

// ---- Stats + skill autocomplete -----------------------------

export async function getStats(): Promise<StatsResponse> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function suggestSkills(q: string): Promise<string[]> {
  const url = new URL(`${API_BASE}/skills`);
  if (q) url.searchParams.set("q", q);
  url.searchParams.set("limit", "8");

  const res = await fetch(url.toString());
  if (!res.ok) return [];   // autocomplete is best-effort; fail silently
  return res.json();
}
