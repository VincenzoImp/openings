import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: "left" | "right";
  className?: string;
  /** Hide the column below the `sm` breakpoint. */
  compact?: boolean;
}

/** A plain table that scrolls horizontally instead of squashing on phones. */
export function Table<T>({
  columns,
  rows,
  rowKey,
  empty = "Nothing to show.",
  minWidth = 520,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  empty?: ReactNode;
  minWidth?: number;
}) {
  if (rows.length === 0) {
    return <p className="px-3 py-3 text-sm text-fg-muted">{empty}</p>;
  }
  return (
    <div
      className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-accent"
      tabIndex={0}
    >
      <table className="w-full text-sm" style={{ minWidth }}>
        <thead className="text-left text-[11px] uppercase tracking-wide text-fg-muted">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-3 py-2 font-medium ${column.align === "right" ? "text-right" : ""} ${column.compact ? "hidden sm:table-cell" : ""} ${column.className ?? ""}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-t border-edge">
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-3 py-2 align-top ${column.align === "right" ? "text-right tabular" : ""} ${column.compact ? "hidden sm:table-cell" : ""} ${column.className ?? ""}`}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
