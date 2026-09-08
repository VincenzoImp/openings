import { useId, useRef, useState } from "react";
import type { DragEvent } from "react";
import { Upload } from "lucide-react";

export function FileDrop({
  onFiles,
  disabled = false,
  label = "Drop files here or choose…",
  hint,
}: {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
  label?: string;
  hint?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const hintId = useId();

  const handle = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (files.length) {
      onFiles(files);
    }
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setOver(false);
    if (!disabled) {
      handle(event.dataTransfer.files);
    }
  };

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={`rounded-md border border-dashed px-3 py-4 text-center text-sm transition-colors ${
        over ? "border-accent bg-accent/8" : "border-edge-strong bg-surface"
      } ${disabled ? "opacity-60" : ""}`}
    >
      <button
        type="button"
        disabled={disabled}
        onClick={() => input.current?.click()}
        aria-describedby={hint ? hintId : undefined}
        className="inline-flex items-center gap-2 text-fg-muted hover:text-fg disabled:cursor-not-allowed"
      >
        <Upload size={16} aria-hidden="true" />
        <span>{label}</span>
      </button>
      {hint ? (
        <p id={hintId} className="mt-1 text-xs text-fg-faint">
          {hint}
        </p>
      ) : null}
      <input
        ref={input}
        type="file"
        multiple
        className="hidden"
        aria-label="Choose files"
        onChange={(event) => {
          handle(event.target.files);
          event.target.value = "";
        }}
      />
    </div>
  );
}
