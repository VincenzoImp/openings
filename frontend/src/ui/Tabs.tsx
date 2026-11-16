import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { X } from "lucide-react";
import { cx } from "./cx";
import { formatNumber } from "./format";
import { Icon, type LucideIcon } from "./Icon";
import { cycleIndex } from "./keys";
import "./tabs.css";

export interface TabItem {
  id: string;
  label: string;
  count?: number;
}

/** Moves focus and selection with the arrow keys, Home and End. */
function useRovingKeys<T extends string>(
  ids: T[],
  value: T,
  onChange: (id: T) => void,
) {
  const ref = useRef<HTMLDivElement>(null);
  function onKeyDown(event: KeyboardEvent) {
    const next = cycleIndex(
      event.key,
      ids.indexOf(value),
      ids.length,
      "horizontal",
    );
    if (next == null) return;
    event.preventDefault();
    onChange(ids[next]);
    ref.current?.querySelectorAll<HTMLElement>("[data-roving]")[next]?.focus();
  }
  return { ref, onKeyDown };
}

/**
 * Underline tabs switch between sets of the same object (New, Shortlist,
 * Dismissed, All), with a count each; at most five. On a phone they become
 * pills in a horizontal scroller. The panel is the caller's: give it
 * `id={panelId}` and `aria-labelledby` the selected tab's `tabId`.
 */
export function Tabs({
  items,
  value,
  onChange,
  label,
  idPrefix,
  className,
}: {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  label: string;
  /** Prefix of the tab ids: `${idPrefix}-tab-${id}`; the panel is `${idPrefix}-panel`. */
  idPrefix: string;
  className?: string;
}) {
  const keys = useRovingKeys(
    items.map((item) => item.id),
    value,
    onChange,
  );
  // Where the tabs scroll (a phone's chips), the selected one is in view.
  const list = keys.ref;
  useEffect(() => {
    const tab = list.current?.querySelector<HTMLElement>(
      '[role="tab"][aria-selected="true"]',
    );
    const box = list.current;
    if (!tab || !box || box.scrollWidth <= box.clientWidth) return;
    box.scrollLeft = Math.max(
      0,
      tab.offsetLeft - (box.clientWidth - tab.offsetWidth) / 2,
    );
  }, [value, list]);
  return (
    <div
      ref={keys.ref}
      className={cx("ui-tabs", className)}
      role="tablist"
      aria-label={label}
      onKeyDown={keys.onKeyDown}
    >
      {items.map((item) => {
        const selected = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            data-roving=""
            id={`${idPrefix}-tab-${item.id}`}
            aria-selected={selected}
            aria-controls={`${idPrefix}-panel`}
            tabIndex={selected ? 0 : -1}
            className="ui-tab"
            onClick={() => onChange(item.id)}
          >
            {item.label}
            {item.count != null && (
              <span className="ui-count">
                {formatNumber(item.count, { compact: true })}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  icon?: LucideIcon;
  /** Shows only the icon; the label stays as the accessible name. */
  iconOnly?: boolean;
}

/**
 * A segmented control switches presentation or a small filter in place
 * (All | Open | Closed). A raised segment on a hover-coloured track.
 */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
}) {
  const keys = useRovingKeys(
    options.map((option) => option.value),
    value,
    onChange,
  );
  return (
    <div
      ref={keys.ref}
      className={cx("ui-segmented", className)}
      role="radiogroup"
      aria-label={label}
      onKeyDown={keys.onKeyDown}
    >
      {options.map((option) => {
        const checked = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            data-roving=""
            aria-checked={checked}
            aria-label={option.iconOnly ? option.label : undefined}
            title={option.iconOnly ? option.label : undefined}
            tabIndex={checked ? 0 : -1}
            className="ui-segment"
            onClick={() => onChange(option.value)}
          >
            {option.icon && <Icon icon={option.icon} size="sm" />}
            {!option.iconOnly && option.label}
          </button>
        );
      })}
    </div>
  );
}

/** The single toolbar row under a page header: tabs left, tools right. */
export function Toolbar({
  children,
  tools,
  label = "View",
}: {
  children?: ReactNode;
  tools?: ReactNode;
  label?: string;
}) {
  return (
    <div className="ui-toolbar" role="toolbar" aria-label={label}>
      {children}
      <span className="ui-toolbar-spacer" />
      {tools && <div className="ui-toolbar-tools">{tools}</div>}
    </div>
  );
}

/**
 * A value as a 26 px pill, the one chip of the system: removable with
 * `onRemove` (a filter, a language, a skill), or a toggle with `onPress` and
 * `pressed`. On a phone its button reaches 44 px.
 */
export function Chip({
  children,
  field,
  onRemove,
  removeLabel,
  onPress,
  pressed = false,
  disabled,
}: {
  children: ReactNode;
  /** The filter's name before its value, in the secondary colour. */
  field?: string;
  onRemove?: () => void;
  removeLabel?: string;
  onPress?: () => void;
  pressed?: boolean;
  disabled?: boolean;
}) {
  if (onPress)
    return (
      <button
        type="button"
        className="ui-chip"
        data-toggle=""
        aria-pressed={pressed}
        disabled={disabled}
        onClick={onPress}
      >
        {children}
      </button>
    );
  return (
    <span className="ui-chip" data-removable={onRemove ? "" : undefined}>
      {field && <span className="ui-chip-field">{field}</span>}
      <span>{children}</span>
      {onRemove && (
        <button
          type="button"
          className="ui-chip-remove"
          aria-label={removeLabel}
          disabled={disabled}
          onClick={onRemove}
        >
          <Icon icon={X} size="sm" />
        </button>
      )}
    </span>
  );
}

export interface FilterChip {
  key: string;
  field: string;
  value: string;
}

/**
 * Active filters as removable chips under the toolbar, then Clear. With no
 * active filter the row does not exist.
 */
export function FilterChips({
  chips,
  onRemove,
  onClear,
  children,
}: {
  chips: FilterChip[];
  onRemove: (key: string) => void;
  onClear: () => void;
  /** An optional trailing control, such as the Filter menu on a phone. */
  children?: ReactNode;
}) {
  if (!chips.length) return null;
  return (
    <div className="ui-chips" role="group" aria-label="Active filters">
      {chips.map((chip) => (
        <Chip
          key={chip.key}
          field={chip.field}
          removeLabel={`Remove filter ${chip.field} ${chip.value}`}
          onRemove={() => onRemove(chip.key)}
        >
          {chip.value}
        </Chip>
      ))}
      {children}
      <button type="button" className="ui-chips-clear" onClick={onClear}>
        Clear
      </button>
    </div>
  );
}
