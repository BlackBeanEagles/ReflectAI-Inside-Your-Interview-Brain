"use client";

// Shared resume-input control (paste text / drag-drop or browse a PDF) used
// by every page that accepts a resume: the interview setup page, Resume
// Analysis, ATS Score, and Predicted Questions. Previously each page
// reimplemented its own paste/upload toggle and a bare <input type="file">
// with no drag-and-drop, no selected-file confirmation, and no way to
// swap files without reopening the OS file picker.

import { useState } from "react";
import { TextArea } from "./ui";
import { useSharedResume, type SharedResume } from "@/lib/resume-context";

function describeResume(r: SharedResume): string {
  if (r.method === "upload" && r.file) return r.file.name;
  const trimmed = r.text.trim();
  return trimmed.length > 60 ? `${trimmed.slice(0, 60)}…` : trimmed;
}

export function ResumePicker({
  method,
  onMethodChange,
  text,
  onTextChange,
  file,
  onFileChange,
  label = "Resume",
  optional = false,
}: {
  method: "paste" | "upload";
  onMethodChange: (m: "paste" | "upload") => void;
  text: string;
  onTextChange: (v: string) => void;
  file: File | null;
  onFileChange: (f: File | null) => void;
  label?: string;
  optional?: boolean;
}) {
  const [dragOver, setDragOver] = useState(false);
  const { lastResume, saveResume } = useSharedResume();

  function acceptFile(files: FileList | null) {
    const f = files?.[0];
    if (f && f.type === "application/pdf") handleFileChange(f);
  }

  // Every edit here is also remembered app-wide (see resume-context.tsx) so
  // whichever page the user fills a resume in next can offer to reuse it,
  // instead of asking them to paste or upload it again.
  function handleTextChange(v: string) {
    onTextChange(v);
    saveResume({ method: "paste", text: v, file: null });
  }

  function handleFileChange(f: File | null) {
    onFileChange(f);
    saveResume({ method: "upload", text: "", file: f });
  }

  const hasCurrentValue = method === "paste" ? text.trim().length > 0 : !!file;

  function applyLastResume() {
    if (!lastResume) return;
    onMethodChange(lastResume.method);
    if (lastResume.method === "paste") onTextChange(lastResume.text);
    else onFileChange(lastResume.file);
  }

  return (
    <div>
      {!hasCurrentValue && lastResume && (
        <button
          type="button"
          onClick={applyLastResume}
          className="mb-3 flex w-full items-center gap-2 rounded-lg border border-ri-info-line bg-ri-info-bg px-3 py-2 text-left text-sm text-ri-info-fg hover:opacity-90"
        >
          <span className="shrink-0">📎</span>
          <span className="min-w-0 flex-1 truncate">
            Use the resume from earlier — <b>{describeResume(lastResume)}</b>
          </span>
          <span className="shrink-0 text-xs font-semibold underline">Use this</span>
        </button>
      )}
      <div className="flex gap-2 mb-3">
        <button
          type="button"
          onClick={() => onMethodChange("paste")}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${method === "paste" ? "bg-ri-accent text-white" : "border border-ri-border"}`}
        >
          Paste text
        </button>
        <button
          type="button"
          onClick={() => onMethodChange("upload")}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${method === "upload" ? "bg-ri-accent text-white" : "border border-ri-border"}`}
        >
          Upload PDF
        </button>
      </div>

      {method === "paste" ? (
        <TextArea
          label={`${label}${optional ? " (optional)" : ""}`}
          value={text}
          onChange={handleTextChange}
          placeholder={"Skills:\nPython, Django, React\n\nProjects:\nChatbot using NLP\n\nExperience:\nInternship"}
          rows={7}
        />
      ) : (
        <div>
          <span className="block text-sm font-medium mb-1.5">
            {label}{optional ? " (optional)" : ""}
          </span>
          {file ? (
            <div className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg border border-ri-border bg-ri-surface-mute text-sm">
              <span className="truncate min-w-0">
                📄 <b>{file.name}</b>{" "}
                <span className="text-ri-text-mute">({(file.size / 1024).toFixed(0)} KB)</span>
              </span>
              <button
                type="button"
                onClick={() => handleFileChange(null)}
                aria-label="Remove file"
                title="Remove file"
                className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-ri-text-mute hover:text-ri-stress hover:bg-ri-surface-alt"
              >
                ✕
              </button>
            </div>
          ) : (
            <label
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                acceptFile(e.dataTransfer.files);
              }}
              className={`flex flex-col items-center justify-center gap-1 px-4 py-8 rounded-lg border-2 border-dashed text-center text-sm cursor-pointer transition-colors ${
                dragOver ? "border-ri-accent bg-ri-info-bg" : "border-ri-border hover:border-ri-accent"
              }`}
            >
              <span className="text-2xl">📄</span>
              <span className="font-medium">Drop a PDF here, or click to browse</span>
              <span className="text-xs text-ri-text-mute">PDF only</span>
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
                className="hidden"
              />
            </label>
          )}
        </div>
      )}
    </div>
  );
}
