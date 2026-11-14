import type { ReactNode } from "react";

/** A row of numbers with their names. */
export function Stats({ children }: { children: ReactNode }) {
  return <dl className="stats num">{children}</dl>;
}
export function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: ReactNode;
  note?: string;
}) {
  return (
    <div className="stat">
      <dt className="caption">{label}</dt>
      <dd>
        <strong>{value}</strong>
        {note && <span className="caption">{note}</span>}
      </dd>
    </div>
  );
}
