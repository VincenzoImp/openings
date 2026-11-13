import type { ReactNode } from "react";
import { SegmentedControl } from "./Tabs";

export interface PaneItem {
  id: string;
  label: string;
  content: ReactNode;
}

/**
 * Panes side by side, such as a posting, a CV and a letter. On narrow screens
 * one pane is shown at a time, chosen with a switch above them; `order` sets
 * the order of the switch when it differs from the order of the panes.
 */
export function Panes({
  label,
  items,
  shown,
  onShow,
  order,
}: {
  label: string;
  items: PaneItem[];
  shown: string;
  onShow: (id: string) => void;
  order?: string[];
}) {
  const options = (order ?? items.map((item) => item.id))
    .map((id) => items.find((item) => item.id === id))
    .filter((item): item is PaneItem => Boolean(item))
    .map(({ id, label }) => ({ id, label }));
  return (
    <>
      <div className="only-mobile pane-switch">
        <SegmentedControl
          label={label}
          value={shown}
          onChange={onShow}
          options={options}
        />
      </div>
      <div className="panes">
        {items.map((item) => (
          <div key={item.id} className="pane" data-shown={item.id === shown}>
            {item.content}
          </div>
        ))}
      </div>
    </>
  );
}
