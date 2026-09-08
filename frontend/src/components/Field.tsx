import type { ComponentProps, ReactNode } from "react";

const CONTROL =
  "w-full min-w-0 rounded-md border border-edge bg-surface px-2 py-1.5 text-sm text-fg placeholder:text-fg-faint focus:border-accent disabled:opacity-60";

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-xs font-medium text-fg-muted">
      {children}
    </label>
  );
}

export function Input({ className = "", ...rest }: ComponentProps<"input">) {
  return <input className={`${CONTROL} h-8 ${className}`} {...rest} />;
}

export function Select({ className = "", ...rest }: ComponentProps<"select">) {
  return <select className={`${CONTROL} h-8 ${className}`} {...rest} />;
}

export function Textarea({ className = "", ...rest }: ComponentProps<"textarea">) {
  return <textarea className={`${CONTROL} min-h-20 ${className}`} {...rest} />;
}

export function Checkbox({
  className = "",
  label,
  ...rest
}: ComponentProps<"input"> & { label: ReactNode }) {
  return (
    <label
      className={`inline-flex cursor-pointer select-none items-center gap-2 text-sm ${className}`}
    >
      <input type="checkbox" className="h-4 w-4 accent-accent" {...rest} />
      {label}
    </label>
  );
}

export function Field({
  label,
  htmlFor,
  children,
  hint,
  className = "",
}: {
  label: string;
  htmlFor?: string;
  children: ReactNode;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={`min-w-0 ${className}`}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint ? <p className="mt-1 text-xs text-fg-faint">{hint}</p> : null}
    </div>
  );
}
