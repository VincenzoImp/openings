import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { Upload } from "lucide-react";

export function FileDrop({
  onFiles,
  disabled = false,
  label = "Drop files here or click to choose",
}: {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
  label?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

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
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
      onClick={() => !disabled && input.current?.click()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          input.current?.click();
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={`flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed px-3 py-4 text-sm ${
        over ? "border-slate-700 bg-slate-100" : "border-slate-300 bg-white"
      } ${disabled ? "cursor-not-allowed opacity-60" : "hover:bg-slate-50"}`}
    >
      <Upload size={16} />
      <span>{label}</span>
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
