import type { ReactNode } from "react";

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-edge-strong bg-surface-2 px-1 text-[11px] font-medium text-fg-muted">
      {children}
    </kbd>
  );
}
