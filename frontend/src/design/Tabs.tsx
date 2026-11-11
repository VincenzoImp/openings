import { useEffect, useRef, type ReactNode } from "react";
import { confirmLeave } from "../state";
import { Icon, type IconName } from "./Icon";
import { nextTabIndex } from "./keys";
import { Count } from "./Tag";

export interface TabItem {
  id: string;
  label: string;
  count?: number;
}
const tabId = (base: string, id: string) => `${base}-tab-${id}`;
const panelId = (base: string) => `${base}-panel`;

/**
 * A tab list with roving focus: arrows, Home and End move and select. With
 * `id` and children (or a separate TabPanel) each tab names the panel it
 * controls. Leaving a tab with unsaved edits asks first.
 */
export function Tabs({
  items,
  value,
  onChange,
  label,
  id,
  children,
}: {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  label: string;
  /** Prefix of the tab and panel ids; needed for a panel. */
  id?: string;
  /** Content of the selected tab, rendered as its panel. */
  children?: ReactNode;
}) {
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const revealSelected = () => {
      const container = list.current;
      const selected = container?.querySelector<HTMLElement>(
        "[aria-selected=true]",
      );
      if (!container || !selected) return;
      const frame = container.getBoundingClientRect();
      const target = selected.getBoundingClientRect();
      if (target.left < frame.left)
        container.scrollLeft -= frame.left - target.left;
      else if (target.right > frame.right)
        container.scrollLeft += target.right - frame.right;
    };
    revealSelected();
    window.addEventListener("resize", revealSelected);
    return () => window.removeEventListener("resize", revealSelected);
  }, [value]);
  return (
    <>
      <div
        ref={list}
        className="tabs"
        role="tablist"
        aria-label={label}
        onKeyDown={(event) => {
          const next = nextTabIndex(
            event.key,
            items.findIndex((item) => item.id === value),
            items.length,
          );
          if (next === null) return;
          event.preventDefault();
          if (!confirmLeave()) return;
          onChange(items[next].id);
          event.currentTarget
            .querySelectorAll<HTMLButtonElement>("[role=tab]")
            [next]?.focus();
        }}
      >
        {items.map((item) => (
          <button
            type="button"
            role="tab"
            id={id && tabId(id, item.id)}
            aria-selected={item.id === value}
            aria-controls={id && panelId(id)}
            tabIndex={item.id === value ? 0 : -1}
            key={item.id}
            onClick={() => {
              if (item.id === value || confirmLeave()) onChange(item.id);
            }}
          >
            {item.label}
            {item.count !== undefined && <Count value={item.count} />}
          </button>
        ))}
      </div>
      {id && children !== undefined && (
        <TabPanel tabs={id} value={value}>
          {children}
        </TabPanel>
      )}
    </>
  );
}

/** The panel of the selected tab of `<Tabs id={tabs}>`. */
export function TabPanel({
  tabs,
  value,
  className,
  children,
}: {
  tabs: string;
  value: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      role="tabpanel"
      id={panelId(tabs)}
      aria-labelledby={tabId(tabs, value)}
      tabIndex={0}
      className={className}
    >
      {children}
    </div>
  );
}

/** A small set of exclusive choices, such as board or list. */
export function SegmentedControl({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { id: string; label: string; icon?: IconName }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          type="button"
          key={option.id}
          aria-pressed={option.id === value}
          onClick={() => onChange(option.id)}
        >
          {option.icon && <Icon name={option.icon} />}
          {option.label}
        </button>
      ))}
    </div>
  );
}
