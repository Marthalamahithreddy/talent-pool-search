"use client";
// =============================================================
// FILE: frontend/components/ProcessingStatus.tsx
// PURPOSE: Shows per-file processing progress for an upload batch.
//          Polls GET /jobs/{jobId} every 2 seconds until the batch
//          is fully complete (status = 'completed' or 'failed').
//
// Props:
//   jobId     → UUID string from the POST /upload response
//   onComplete → called when all files are processed
// =============================================================

import { useEffect, useState } from "react";
import { CheckCircle, XCircle, Loader2, Clock, Copy } from "lucide-react";
import { getJobStatus } from "@/lib/api";
import type { JobStatusResponse, ResumeStatus } from "@/lib/types";

interface Props {
  jobId: string;
  onComplete: () => void;
}

export default function ProcessingStatus({ jobId, onComplete }: Props) {
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Poll every 2 seconds
    const poll = async () => {
      try {
        const data = await getJobStatus(jobId);
        setJob(data);

        if (data.status === "completed" || data.status === "failed") {
          onComplete();
          return;   // stop polling
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to fetch job status");
        return;     // stop polling on network error
      }

      setTimeout(poll, 2000);
    };

    poll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Loader2 className="w-4 h-4 animate-spin" />
        Connecting…
      </div>
    );
  }

  const pct = job.total_files > 0
    ? Math.round((job.processed_files / job.total_files) * 100)
    : 0;

  return (
    <div className="space-y-4">
      {/* Overall progress bar */}
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>{job.processed_files} of {job.total_files} processed</span>
          <span>{pct}%</span>
        </div>
        <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-brand-500 transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Per-file status rows */}
      <ul className="space-y-2">
        {job.resumes.map((r) => (
          <FileRow key={r.resume_id} resume={r} />
        ))}
      </ul>

      {/* Processing summary + done banner (shown once the batch finishes) */}
      {(job.status === "completed" || job.status === "failed") && (
        <ProcessingSummary resumes={job.resumes} />
      )}
    </div>
  );
}

// Counts of each terminal status, shown after the batch finishes
function ProcessingSummary({ resumes }: { resumes: ResumeStatus[] }) {
  const total      = resumes.length;
  const successful = resumes.filter((r) => r.processing_status === "completed").length;
  const duplicates = resumes.filter((r) => r.processing_status === "duplicate").length;
  const failed     = resumes.filter((r) => r.processing_status === "failed").length;

  return (
    <div className="rounded-lg bg-gray-50 border border-gray-200 p-4 space-y-3">
      <div className="flex flex-wrap gap-4 text-sm">
        <span className="text-gray-600"><strong>{total}</strong> uploaded</span>
        <span className="text-green-700"><strong>{successful}</strong> successful</span>
        {duplicates > 0 && (
          <span className="text-amber-600"><strong>{duplicates}</strong> duplicate{duplicates !== 1 ? "s" : ""}</span>
        )}
        {failed > 0 && (
          <span className="text-red-600"><strong>{failed}</strong> failed</span>
        )}
      </div>

      {successful + duplicates > 0 && (
        <div className="text-sm text-gray-600">
          Head to{" "}
          <a href="/candidates" className="text-brand-600 underline font-medium">Search Candidates</a>{" "}
          to explore them.
        </div>
      )}
    </div>
  );
}

function FileRow({ resume }: { resume: ResumeStatus }) {
  const icon = {
    pending:    <Clock className="w-4 h-4 text-gray-400" />,
    processing: <Loader2 className="w-4 h-4 text-brand-500 animate-spin" />,
    completed:  <CheckCircle className="w-4 h-4 text-green-500" />,
    failed:     <XCircle className="w-4 h-4 text-red-500" />,
    duplicate:  <Copy className="w-4 h-4 text-amber-500" />,
  }[resume.processing_status];

  const label = {
    pending:    "text-gray-400",
    processing: "text-brand-600",
    completed:  "text-green-700",
    failed:     "text-red-600",
    duplicate:  "text-amber-600",
  }[resume.processing_status];

  return (
    <li className="flex items-center gap-3 rounded-lg border border-gray-100 bg-white px-3 py-2 shadow-sm">
      {icon}
      <span className="flex-1 text-sm text-gray-700 truncate">{resume.original_filename}</span>
      <span className={`text-xs font-medium capitalize ${label}`}>
        {resume.processing_status}
      </span>
      {resume.error_message && (
        <span className="text-xs text-red-500 truncate max-w-xs" title={resume.error_message}>
          {resume.error_message}
        </span>
      )}
    </li>
  );
}
