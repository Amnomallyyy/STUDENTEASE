import { useId, useRef, useState, type DragEvent } from "react";
import { FileText, UploadCloud, X } from "lucide-react";

interface Props {
  file: File | null;
  onFile: (file: File | null) => void;
  accept?: string[];
  maxBytes?: number;
  disabled?: boolean;
  label?: string;
}

export const CV_EXTENSIONS = [".pdf", ".docx", ".txt"];
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

/** Validate a file against the accepted extensions and size; returns an error message or null. */
export function validateFile(file: File, accept = CV_EXTENSIONS, maxBytes = MAX_UPLOAD_BYTES): string | null {
  if (!accept.includes(extensionOf(file.name))) {
    return `Unsupported file type. Use ${accept.join(", ")}.`;
  }
  if (file.size > maxBytes) return `File is larger than ${Math.round(maxBytes / 1024 / 1024)} MB.`;
  if (file.size === 0) return "The file is empty.";
  return null;
}

export default function CVDropzone({
  file,
  onFile,
  accept = CV_EXTENSIONS,
  maxBytes = MAX_UPLOAD_BYTES,
  disabled,
  label = "Drop your CV here, or click to choose a file",
}: Props) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function pick(candidate: File | undefined) {
    if (!candidate) return;
    const problem = validateFile(candidate, accept, maxBytes);
    setError(problem);
    onFile(problem ? null : candidate);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    pick(event.dataTransfer.files?.[0]);
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
          dragging ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white hover:border-brand-400"
        } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
      >
        <input
          id={inputId}
          ref={inputRef}
          type="file"
          accept={accept.join(",")}
          className="sr-only"
          disabled={disabled}
          onChange={(e) => {
            pick(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        {file ? (
          <>
            <FileText className="h-8 w-8 text-brand-600" aria-hidden />
            <p className="text-sm font-medium text-slate-800">{file.name}</p>
            <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(0)} KB</p>
            <button
              type="button"
              className="btn-ghost text-xs"
              onClick={(e) => {
                e.stopPropagation();
                setError(null);
                onFile(null);
              }}
            >
              <X className="h-3 w-3" aria-hidden /> Remove
            </button>
          </>
        ) : (
          <>
            <UploadCloud className="h-8 w-8 text-slate-400" aria-hidden />
            <p className="text-sm font-medium text-slate-700">{label}</p>
            <p className="text-xs text-slate-500">
              {accept.join(", ")} up to {Math.round(maxBytes / 1024 / 1024)} MB
            </p>
          </>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
