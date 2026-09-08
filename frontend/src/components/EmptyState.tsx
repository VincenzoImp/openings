import type { ReactNode } from "react";

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-edge-strong px-4 py-10 text-center">
      <p className="text-sm font-medium text-fg">{title}</p>
      {children ? <div className="max-w-md text-xs text-fg-muted">{children}</div> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-fg-muted">
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-edge-strong border-t-fg" />
      {label}
    </div>
  );
}

export function Skeleton({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`animate-pulse space-y-2 ${className}`} aria-hidden="true">
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="h-3 rounded bg-surface-2"
          style={{ width: `${85 - (index % 3) * 15}%` }}
        />
      ))}
    </div>
  );
}

export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div
      role="alert"
      className="flex items-center justify-between gap-3 rounded-md border border-negative/40 bg-negative/8 px-3 py-2 text-sm text-negative"
    >
      <span className="min-w-0 break-words">{message}</span>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="shrink-0 underline">
          Retry
        </button>
      ) : null}
    </div>
  );
}
