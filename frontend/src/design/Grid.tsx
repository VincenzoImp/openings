import type { CSSProperties, ReactNode } from "react";
import { cx } from "./classes";

/**
 * A table built from rows of a CSS grid, with the ARIA roles of a table. The
 * roles keep its meaning for screen readers when narrow screens stack each row
 * into a block, and each row is skipped by layout and paint while it is off
 * screen (`content-visibility`), so a list of hundreds of rows stays fast.
 * `columns` are the grid columns of every row on wide screens.
 */
export function GridTable({
  label,
  columns,
  head,
  className,
  children,
}: {
  label: string;
  columns: string;
  /** Column names, shown or for screen readers only, or a control. */
  head: { name: string; hidden?: boolean; content?: ReactNode }[];
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid-wrap">
      <div
        role="table"
        aria-label={label}
        className={cx("grid-table", className)}
        style={{ "--cols": columns } as CSSProperties}
      >
        <div role="rowgroup" className="grid-head">
          <div role="row" className="grid-row">
            {head.map((column, index) => (
              <div role="columnheader" key={index}>
                {column.content ??
                  (column.hidden ? (
                    <span className="sr">{column.name}</span>
                  ) : (
                    column.name
                  ))}
              </div>
            ))}
          </div>
        </div>
        <div role="rowgroup">{children}</div>
      </div>
    </div>
  );
}

/** One row; `selected` marks a row the owner picked for a bulk action. */
export function GridRow({
  selected = false,
  className,
  id,
  children,
}: {
  selected?: boolean;
  className?: string;
  id?: string;
  children: ReactNode;
}) {
  return (
    <div
      role="row"
      id={id}
      className={cx("grid-row", selected && "is-selected", className)}
    >
      {children}
    </div>
  );
}

/**
 * One cell. `label` names it when the row is stacked on a narrow screen;
 * `kind` places it: the row's title, a full-width block, or the actions.
 */
export function Cell({
  label,
  kind,
  className,
  children,
}: {
  label?: string;
  kind?: "primary" | "full" | "actions" | "select";
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div
      role="cell"
      data-label={label}
      className={cx(kind, className)}
      data-empty={
        children === undefined ||
        children === null ||
        children === false ||
        children === "" ||
        undefined
      }
    >
      {children}
    </div>
  );
}
