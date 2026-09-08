"use client";

// Shared resume-input control (paste text / drag-drop or browse a PDF) used
// by every page that accepts a resume: the interview setup page, Resume
// Analysis, ATS Score, and Predicted Questions. Previously each page
// reimplemented its own paste/upload toggle and a bare <input type="file">
// with no drag-and-drop, no selected-file confirmation, and no way to
// swap files without reopening the OS file picker.

import { useState } from "react";
import { FileText, Paperclip, Upload, X } from "lucide-react";
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
          className="ri-focus mb-3 flex w-full items-center gap-2 rounded-lg border border-ri-border bg-ri-surface-alt px-3 py-2 text-left text-sm transition-colors hover:border-ri-border-strong"
        >
          <Paperclip size={14} strokeWidth={1.75} className="shrink-0 text-ri-text-mute" aria-hidden />
          <span className="min-w-0 flex-1 truncate">
            Use the resume from earlier — <b>{describeResume(lastResume)}</b>
          </span>
          <span className="shrink-0 text-xs font-semibold underline">Use this</span>
        </button>
      )}
      {/* A segmented control rather than two loose buttons: these are two
          states of one choice, so they should share an enclosure. */}
      <div
        role="tablist"
        aria-label="Resume input method"
        className="mb-3 inline-flex rounded-lg border border-ri-border bg-ri-surface-alt p-0.5"
      >
        {(["paste", "upload"] as const).map((m) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={method === m}
            onClick={() => onMethodChange(m)}
            className={`ri-focus rounded-[6px] px-3 py-1 text-[13px] font-medium transition-colors ${
              method === m
                ? "bg-ri-surface text-ri-text shadow-[var(--ri-shadow)]"
                : "text-ri-text-mute hover:text-ri-text"
            }`}
          >
            {m === "paste" ? "Paste text" : "Upload PDF"}
          </button>
        ))}
      </div>

      {method === "paste" ? (
        <TextArea
          label={`${label}${optional ? " (optional)" : ""}`}
          value={text}
          onChange={handleTextChange}
          placeholder={"Skills:\nPython, Django, React\n\nProjects:\nChatbot using NLP\n\nExperience:\nInternship"}
          // The placeholder is 8 lines; at 7 rows its last line is clipped,
          // which reads as a broken field rather than an example.
          rows={8}
        />
      ) : (
        <div>
          <span className="block text-sm font-medium mb-1.5">
            {label}{optional ? " (optional)" : ""}
          </span>
          {file ? (
            <div className="flex items-center gap-2.5 rounded-lg border border-ri-border bg-ri-surface px-3 py-2.5 text-sm">
              <FileText size={15} strokeWidth={1.75} className="shrink-0 text-ri-text-mute" aria-hidden />
              <span className="min-w-0 flex-1 truncate">
                {file.name}{" "}
                <span className="text-ri-text-mute">({(file.size / 1024).toFixed(0)} KB)</span>
              </span>
              <button
                type="button"
                onClick={() => handleFileChange(null)}
                aria-label="Remove file"
                title="Remove file"
                className="ri-focus flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-ri-text-mute transition-colors hover:bg-ri-surface-alt hover:text-ri-text"
              >
                <X size={14} strokeWidth={2} aria-hidden />
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
              className={`flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed px-4 py-9 text-center text-sm transition-colors ${
                dragOver
                  ? "border-ri-accent bg-ri-accent-soft"
                  : "border-ri-border-strong hover:border-ri-accent hover:bg-ri-surface-alt"
              }`}
            >
              <Upload size={18} strokeWidth={1.5} className="text-ri-text-mute" aria-hidden />
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
