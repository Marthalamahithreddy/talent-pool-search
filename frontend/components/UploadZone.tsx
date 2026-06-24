"use client";
// =============================================================
// FILE: frontend/components/UploadZone.tsx
// PURPOSE: Drag-and-drop file upload area.
//          Accepts multiple PDF or DOCX files via drag-drop or
//          click-to-browse. Validates file types client-side
//          before passing them up to the parent via onFilesSelected.
//
// Props:
//   onFilesSelected(files: File[]) → called when valid files are picked
//   disabled                       → true while upload is in progress
// =============================================================

import { useRef, useState, DragEvent, ChangeEvent } from "react";
import { UploadCloud } from "lucide-react";
import { clsx } from "clsx";

interface Props {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

const ACCEPTED_TYPES = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
const ACCEPTED_EXTENSIONS = [".pdf", ".docx"];

export default function UploadZone({ onFilesSelected, disabled = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) return;
    processFiles(Array.from(e.dataTransfer.files));
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    if (e.target.files) {
      processFiles(Array.from(e.target.files));
      // Reset input so re-selecting the same file triggers onChange again
      e.target.value = "";
    }
  }

  function processFiles(files: File[]) {
    setError(null);
    const valid: File[] = [];
    const rejected: string[] = [];

    for (const file of files) {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (ACCEPTED_TYPES.includes(file.type) || ACCEPTED_EXTENSIONS.includes(ext)) {
        valid.push(file);
      } else {
        rejected.push(file.name);
      }
    }

    if (rejected.length > 0) {
      setError(`Unsupported file type(s): ${rejected.join(", ")}. Only PDF and DOCX are accepted.`);
    }

    if (valid.length > 0) {
      onFilesSelected(valid);
    }
  }

  return (
    <div className="w-full">
      <div
        onClick={() => !disabled && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        className={clsx(
          "flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl p-12 cursor-pointer transition-all",
          isDragOver
            ? "border-brand-500 bg-brand-50"
            : "border-gray-300 bg-white hover:border-brand-400 hover:bg-brand-50",
          disabled && "opacity-50 cursor-not-allowed"
        )}
      >
        <UploadCloud className="w-10 h-10 text-brand-500" />
        <p className="text-base font-medium text-gray-700">
          Drag & drop resumes here, or <span className="text-brand-600 underline">browse</span>
        </p>
        <p className="text-sm text-gray-400">PDF and DOCX — multiple files supported</p>
      </div>

      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.docx"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />

      {error && (
        <p className="mt-2 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
