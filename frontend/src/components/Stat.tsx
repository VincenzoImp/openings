import type { ReactNode } from "react";

import { formatNumber } from "../features/shared/format";

export function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | string;
  hint?: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <div className="truncate text-[11px] uppercase tracking-wide text-fg-muted">{label}</div>
      <div className="tabular text-xl font-semibold leading-tight text-fg">
        {typeof value === "number" ? formatNumber(value) : value}
      </div>
      {hint ? <div className="text-xs text-fg-faint">{hint}</div> : null}
    </div>
  );
}
