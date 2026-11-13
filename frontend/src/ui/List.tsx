import {
  createContext,
  useContext,
  useId,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { IconButton } from "./Button";
import { cx } from "./cx";
import type { LucideIcon } from "./Icon";
import { listIndex, plainKey } from "./keys";
import "./list.css";

interface ListState {
  activeId: string | null;
  onActiveChange: (id: string) => void;
}
const ListContext = createContext<ListState | null>(null);

/**
 * A full-bleed list of records with one keyboard model: `j`/`k` or the
 * arrows move the selection, Home and End jump, Enter opens, and letters run
 * the row shortcuts (`s` shortlist, `d` dismiss…) on the selected row. Only
 * the selected row is a Tab stop; its actions follow it.
 */
export function List({
  label,
  activeId,
  onActiveChange,
  onOpen,
  shortcuts = {},
  children,
  className,
}: {
  label: string;
  /** The selected row, or the first one: the list's Tab stop. */
  activeId: string | null;
  onActiveChange: (id: string) => void;
  onOpen?: (id: string) => void;
  shortcuts?: Record<string, (id: string) => void>;
  children: ReactNode;
  className?: string;
}) {
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const key = plainKey(event.nativeEvent);
    if (!key) return;
    const rows = [
      ...event.currentTarget.querySelectorAll<HTMLElement>("[data-row-id]"),
    ];
    const ids = rows.map((row) => row.dataset.rowId!);
    const focused = (event.target as HTMLElement).closest<HTMLElement>(
      "[data-row-id]",
    );
    const current = focused
      ? ids.indexOf(focused.dataset.rowId!)
      : ids.indexOf(activeId ?? "");
    const next = listIndex(key, current, ids.length);
    if (next != null) {
      event.preventDefault();
      onActiveChange(ids[next]);
      rows[next].focus();
      rows[next].scrollIntoView({ block: "nearest" });
      return;
    }
    const id = ids[current];
    if (!id) return;
    if (key === "Enter" && onOpen && focused === event.target) {
      event.preventDefault();
      onOpen(id);
      return;
    }
    const run = shortcuts[key.toLowerCase()];
    if (run && key.length === 1) {
      event.preventDefault();
      run(id);
    }
  }
  return (
    <ListContext.Provider value={{ activeId, onActiveChange }}>
      <div
        className={cx("ui-list", className)}
        role="region"
        aria-label={label}
        onKeyDown={onKeyDown}
      >
        {children}
      </div>
    </ListContext.Provider>
  );
}

/** Rows under a sticky 32 px header: "Today 4". */
export function ListGroup({
  label,
  count,
  children,
}: {
  label: string;
  count?: number;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section className="ui-list-group" aria-labelledby={id}>
      <h3 className="ui-list-head" id={id}>
        {label}
        {count != null && <span className="ui-count">{count}</span>}
      </h3>
      <ul className="ui-list-rows">{children}</ul>
    </section>
  );
}

/** Rows without a group header. */
export function ListRows({ children }: { children: ReactNode }) {
  return <ul className="ui-list-rows">{children}</ul>;
}

export interface RowAction {
  label: string;
  icon: LucideIcon;
  shortcut?: string;
  onClick: () => void;
}

/**
 * One record on one or two lines: a leading dot or status glyph, the title
 * (one line, ellipsis), a sub-line, and one trailing meta. On hover, focus or
 * selection the meta gives way to one or two icon actions. Selected rows get
 * the selected fill and a 2 px accent bar.
 */
export function ListRow({
  id,
  title,
  sub,
  leading,
  meta,
  actions = [],
  href,
  dense = false,
}: {
  id: string;
  title: ReactNode;
  sub?: ReactNode;
  leading?: ReactNode;
  meta?: ReactNode;
  actions?: RowAction[];
  /** A link row (opens a page) instead of a selecting row. */
  href?: string;
  dense?: boolean;
}) {
  const list = useContext(ListContext);
  const selected = list?.activeId === id;
  const body = (
    <>
      <span className="ui-row-lead">{leading}</span>
      <span className="ui-row-text">
        <span className="ui-row-title">{title}</span>
        {sub && <span className="ui-row-sub">{sub}</span>}
      </span>
    </>
  );
  const common = {
    className: "ui-row-main",
    "data-row-id": id,
    tabIndex: list ? (selected ? 0 : -1) : 0,
    "aria-current": selected ? ("true" as const) : undefined,
    onClick: () => list?.onActiveChange(id),
  };
  return (
    <li
      className="ui-row"
      data-selected={selected || undefined}
      data-dense={dense || undefined}
      data-has-actions={actions.length ? "" : undefined}
    >
      {href ? (
        <a href={href} {...common}>
          {body}
        </a>
      ) : (
        <button type="button" {...common}>
          {body}
        </button>
      )}
      {(meta || actions.length > 0) && (
        <span className="ui-row-end">
          {meta && <span className="ui-row-meta">{meta}</span>}
          {actions.length > 0 && (
            <span className="ui-row-actions">
              {actions.slice(0, 2).map((action) => (
                <IconButton
                  key={action.label}
                  icon={action.icon}
                  label={action.label}
                  shortcut={action.shortcut}
                  size="sm"
                  raised
                  tabIndex={selected ? 0 : -1}
                  tooltip="above"
                  onClick={action.onClick}
                />
              ))}
            </span>
          )}
        </span>
      )}
    </li>
  );
}
