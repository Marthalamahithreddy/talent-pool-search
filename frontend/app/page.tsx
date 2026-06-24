"use client";
// =============================================================
// FILE: frontend/app/page.tsx
// PURPOSE: Page 1 — Upload.
//          Users drag-drop or browse for resume files (PDF/DOCX).
//          On submit: calls POST /upload, then shows per-file
//          progress using ProcessingStatus with 2-second polling.
// =============================================================

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import UploadZone from "@/components/UploadZone";
import ProcessingStatus from "@/components/ProcessingStatus";
import { uploadResumes } from "@/lib/api";

type PageState = "idle" | "uploading" | "processing" | "done";

export default function UploadPage() {
  const router = useRouter();

  const [state, setState] = useState<PageState>("idle");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Called by UploadZone when valid files are picked
  function handleFilesSelected(files: File[]) {
    setPendingFiles((prev) => {
      // Merge — deduplicate by name
      const existingNames = new Set(prev.map((f) => f.name));
      const newFiles = files.filter((f) => !existingNames.has(f.name));
      return [...prev, ...newFiles];
    });
    setUploadError(null);
  }

  function removeFile(name: string) {
    setPendingFiles((prev) => prev.filter((f) => f.name !== name));
  }

  async function handleUpload() {
    if (pendingFiles.length === 0) return;

    setState("uploading");
    setUploadError(null);

    try {
      const response = await uploadResumes(pendingFiles);
      setJobId(response.job_id);
      setState("processing");
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Upload failed. Please try again.");
      setState("idle");
    }
  }

  function handleProcessingComplete() {
    setState("done");
  }

  // ---- Render -----------------------------------------------

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Resumes</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload PDF or DOCX resumes. Contact details are extracted locally; AI only sees anonymised text.
        </p>
      </div>

      {/* Upload zone — hidden while processing */}
      {state === "idle" || state === "uploading" ? (
        <>
          <UploadZone onFilesSelected={handleFilesSelected} disabled={state === "uploading"} />

          {/* Staged file list */}
          {pendingFiles.length > 0 && (
            <ul className="space-y-2">
              {pendingFiles.map((f) => (
                <li
                  key={f.name}
                  className="flex items-center justify-between rounded-lg border border-gray-100 bg-white px-3 py-2 shadow-sm text-sm"
                >
                  <span className="truncate text-gray-700">{f.name}</span>
                  <button
                    onClick={() => removeFile(f.name)}
                    className="ml-4 text-xs text-red-500 hover:text-red-700"
                    disabled={state === "uploading"}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}

          {uploadError && (
            <p className="text-sm text-red-600">{uploadError}</p>
          )}

          <button
            onClick={handleUpload}
            disabled={pendingFiles.length === 0 || state === "uploading"}
            className="w-full py-3 rounded-lg bg-brand-600 text-white font-semibold hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            {state === "uploading" ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Uploading…
              </>
            ) : (
              `Process ${pendingFiles.length} Resume${pendingFiles.length !== 1 ? "s" : ""}`
            )}
          </button>
        </>
      ) : null}

      {/* Progress tracker */}
      {(state === "processing" || state === "done") && jobId && (
        <ProcessingStatus jobId={jobId} onComplete={handleProcessingComplete} />
      )}

      {/* After done — offer to start a new batch */}
      {state === "done" && (
        <div className="flex gap-3">
          <button
            onClick={() => {
              setState("idle");
              setPendingFiles([]);
              setJobId(null);
            }}
            className="flex-1 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Upload More
          </button>
          <button
            onClick={() => router.push("/candidates")}
            className="flex-1 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 transition-colors"
          >
            View All Candidates →
          </button>
        </div>
      )}
    </div>
  );
}
