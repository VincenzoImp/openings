import type { ReactNode } from "react";

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex min-w-[1.4rem] items-center justify-center rounded border border-slate-300 bg-slate-50 px-1 text-[11px] font-medium text-slate-700">
      {children}
    </kbd>
  );
}
