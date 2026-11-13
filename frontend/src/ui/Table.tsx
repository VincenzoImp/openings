import type { ReactNode } from "react";
import { EMPTY } from "./format";
import "./table.css";

export interface Column<Row> {
  key: string;
  label: string;
  /** Numbers are right-aligned with tabular figures. */
  numeric?: boolean;
  value: (row: Row) => ReactNode;
}

const blank = (value: ReactNode) =>
  value == null || value === "" || value === false;

/**
 * A table for comparing across columns (providers, stats), not for browsing
 * records. 40 px rows with hairlines, no zebra; an empty cell is a dash, and
 * a column empty in every row is not rendered.
 */
export function Table<Row>({
  columns,
  rows,
  rowKey,
  caption,
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  /** The accessible name; visually hidden. */
  caption: string;
}) {
  const shown = columns.filter((column) =>
    rows.some((row) => !blank(column.value(row))),
  );
  return (
    <div className="ui-table-wrap">
      <table className="ui-table">
        <caption className="ui-sr">{caption}</caption>
        <thead>
          <tr>
            {shown.map((column) => (
              <th
                key={column.key}
                scope="col"
                data-numeric={column.numeric || undefined}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {shown.map((column) => {
                const value = column.value(row);
                return (
                  <td
                    key={column.key}
                    data-numeric={column.numeric || undefined}
                  >
                    {blank(value) ? (
                      <span className="ui-table-empty">{EMPTY}</span>
                    ) : (
                      value
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
