// =============================================================
// FILE: frontend/lib/types.ts
// PURPOSE: TypeScript types that mirror the FastAPI Pydantic schemas.
//          Keep these in sync with backend/models/schemas.py.
//
// Types:
//   UploadJobResponse   → returned by POST /upload
//   ResumeStatus        → one file's status inside a job
//   JobStatusResponse   → returned by GET /jobs/{job_id}
//   CandidateCard       → compact view in search results
//   CandidateDetail     → full candidate profile
// =============================================================

export interface UploadJobResponse {
  job_id: string;
  total_files: number;
  message: string;
}

export type ProcessingStatusValue =
  | "pending"
  | "processing"
  | "completed"
  | "failed"
  | "duplicate";   // identical resume already in the pool

export interface ResumeStatus {
  resume_id: string;
  original_filename: string;
  processing_status: ProcessingStatusValue;
  error_message: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  total_files: number;
  processed_files: number;
  resumes: ResumeStatus[];
}

export interface CandidateCard {
  id: string;
  name: string | null;
  location: string | null;
  years_experience: number | null;
  current_title: string | null;
  skills: string[];
}

export interface CandidateDetail {
  id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  location: string | null;
  years_experience: number | null;
  current_title: string | null;
  skills: string[];
  s3_url: string | null;
  created_at: string | null;
}

export interface SearchParams {
  skill?: string;
  location?: string;
  min_exp?: number;
}

export interface StatsResponse {
  total_candidates: number;
  total_locations: number;
  total_skills: number;
  avg_experience: number | null;
}
