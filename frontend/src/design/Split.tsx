import type { CSSProperties, ReactNode } from "react";
import { SegmentedControl } from "./Tabs";

/**
 * A list beside its detail panel. On narrow screens one of the two is shown,
 * chosen with a switch above them; `pane` and `onPane` hold that choice, so
 * opening a row can show the detail. Without `labels` both simply stack.
 */
export function Split({
  columns,
  labels,
  pane = 0,
  onPane,
  children,
}: {
  /** The grid columns on wide screens: "minmax(0, 1fr) minmax(0, 1.25fr)". */
  columns?: string;
  /** Names of the two panes for the switch: ["Record", "Selected entry"]. */
  labels?: [string, string];
  pane?: 0 | 1;
  onPane?: (pane: 0 | 1) => void;
  /** Exactly two elements: the list and the detail. */
  children: ReactNode;
}) {
  return (
    <>
      {labels && onPane && (
        <div className="only-mobile split-switch">
          <SegmentedControl
            label="Shown pane"
            value={String(pane)}
            onChange={(id) => onPane(id === "1" ? 1 : 0)}
            options={[
              { id: "0", label: labels[0] },
              { id: "1", label: labels[1] },
            ]}
          />
        </div>
      )}
      <div
        className="split"
        data-pane={labels ? pane : undefined}
        style={columns ? ({ "--split": columns } as CSSProperties) : undefined}
      >
        {children}
      </div>
    </>
  );
}
