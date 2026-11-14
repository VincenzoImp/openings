import {
  createContext,
  useCallback,
  useContext,
  useId,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { Check } from "lucide-react";
import { Button, IconButton } from "./Button";
import { cx } from "./cx";
import {
  LONG_PRESS_MS,
  PRESS_SLOP,
  selectRange,
  swipeOutcome,
  toggleSelected,
} from "./gestures";
import { Icon, type LucideIcon } from "./Icon";
import { listIndex, plainKey } from "./keys";
import "./list.css";

/** The rows picked for a bulk action, and how to change them. */
export interface Selection {
  ids: ReadonlySet<string>;
  /** `x` or ⌘-click on a row. */
  toggle: (id: string) => void;
  /** Shift-click: from the last toggled row to `id`, in `order`. */
  extend: (order: readonly string[], id: string) => void;
  clear: () => void;
}

/** Multi-select state for a List: pass it as `selection`. */
export function useSelection(): Selection {
  const [ids, setIds] = useState<ReadonlySet<string>>(() => new Set());
  const anchor = useRef<string | null>(null);
  const toggle = useCallback((id: string) => {
    anchor.current = id;
    setIds((current) => toggleSelected(current, id));
  }, []);
  const extend = useCallback((order: readonly string[], id: string) => {
    const from = anchor.current;
    setIds((current) => selectRange(current, order, from, id));
    anchor.current = id;
  }, []);
  const clear = useCallback(() => {
    anchor.current = null;
    setIds(new Set());
  }, []);
  return useMemo(
    () => ({ ids, toggle, extend, clear }),
    [ids, toggle, extend, clear],
  );
}

interface ListState {
  activeId: string | null;
  onActiveChange: (id: string) => void;
  selection?: Selection;
}
const ListContext = createContext<ListState | null>(null);

const rowIds = (from: Element | null) =>
  [
    ...(from
      ?.closest(".ui-list")
      ?.querySelectorAll<HTMLElement>("[data-row-id]") ?? []),
  ].map((row) => row.dataset.rowId!);

/**
 * A full-bleed list of records with one keyboard model: `j`/`k` or the
 * arrows move the selection, Home and End jump, Enter opens, and letters run
 * the row shortcuts (`s` shortlist, `d` dismiss…) on the selected row. Only
 * the selected row is a Tab stop; its actions follow it. With a `selection`,
 * `x` and ⌘-click pick rows, shift-click picks a range and Esc clears.
 */
export function List({
  label,
  activeId,
  onActiveChange,
  onOpen,
  shortcuts = {},
  selection,
  children,
  className,
}: {
  label: string;
  /** The selected row, or the first one: the list's Tab stop. */
  activeId: string | null;
  onActiveChange: (id: string) => void;
  onOpen?: (id: string) => void;
  shortcuts?: Record<string, (id: string) => void>;
  selection?: Selection;
  children: ReactNode;
  className?: string;
}) {
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const key = plainKey(event.nativeEvent);
    // A row's open menu keeps its own keys.
    if (!key || (event.target as HTMLElement).closest?.("[role=menu]")) return;
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
    if (key === "Escape" && selection?.ids.size) {
      event.preventDefault();
      selection.clear();
      return;
    }
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
    if (key === "x" && selection) {
      event.preventDefault();
      selection.toggle(id);
      return;
    }
    const run = shortcuts[key.toLowerCase()];
    if (run && key.length === 1) {
      event.preventDefault();
      run(id);
    }
  }
  return (
    <ListContext.Provider value={{ activeId, onActiveChange, selection }}>
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
 * Touch gestures of a row: a horizontal drag past the threshold runs the
 * right (shortlist) or left (dismiss) action; a press held still opens the
 * row's menu. Mouse and pen keep the hover actions and shortcuts.
 */
function useSwipe(
  swipe: { left?: RowAction; right?: RowAction } | undefined,
  onLongPress: (() => void) | undefined,
) {
  const [dx, setDx] = useState(0);
  const start = useRef<{ x: number; y: number; width: number } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pressed = useRef(false);
  const stopTimer = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };
  const enabled = Boolean(swipe?.left || swipe?.right || onLongPress);
  if (!enabled) return { dx: 0, handlers: {}, pressed };
  const reset = () => {
    stopTimer();
    start.current = null;
    setDx(0);
  };
  const handlers = {
    onPointerDown(event: PointerEvent<HTMLLIElement>) {
      if (event.pointerType !== "touch") return;
      pressed.current = false;
      start.current = {
        x: event.clientX,
        y: event.clientY,
        width: event.currentTarget.offsetWidth,
      };
      if (onLongPress)
        timer.current = setTimeout(() => {
          pressed.current = true;
          start.current = null;
          setDx(0);
          onLongPress();
        }, LONG_PRESS_MS);
    },
    onPointerMove(event: PointerEvent<HTMLLIElement>) {
      const from = start.current;
      if (!from) return;
      const moveX = event.clientX - from.x;
      const moveY = event.clientY - from.y;
      if (Math.hypot(moveX, moveY) > PRESS_SLOP) stopTimer();
      if (Math.abs(moveY) > Math.abs(moveX)) return;
      // Only toward a side that has an action.
      if ((moveX > 0 && !swipe?.right) || (moveX < 0 && !swipe?.left))
        return setDx(0);
      setDx(moveX);
    },
    onPointerUp(event: PointerEvent<HTMLLIElement>) {
      const from = start.current;
      reset();
      if (!from) return;
      const side = swipeOutcome(
        event.clientX - from.x,
        event.clientY - from.y,
        from.width,
      );
      const action =
        side === "right" ? swipe?.right : side ? swipe?.left : null;
      if (action) {
        pressed.current = true;
        action.onClick();
      }
    },
    onPointerCancel: reset,
  };
  return { dx, handlers, pressed };
}

/**
 * One record on one or two lines: a leading dot or status glyph, the title
 * (one line, ellipsis), a sub-line, and one trailing meta. On hover, focus or
 * selection the meta gives way to one or two icon actions. Selected rows get
 * the selected fill and a 2 px accent bar; rows picked for a bulk action
 * show a check. On touch, `swipe` and `onLongPress` replace hover actions.
 */
export function ListRow({
  id,
  title,
  sub,
  leading,
  meta,
  actions = [],
  swipe,
  onLongPress,
  href,
  menu,
  dense = false,
}: {
  id: string;
  title: ReactNode;
  sub?: ReactNode;
  leading?: ReactNode;
  meta?: ReactNode;
  actions?: RowAction[];
  /** Touch: drag right or left to run an action (shortlist, dismiss). */
  swipe?: { left?: RowAction; right?: RowAction };
  /** Touch: a long press, usually the row's menu. */
  onLongPress?: () => void;
  /** A link row (opens a page) instead of a selecting row. */
  href?: string;
  /**
   * The row's `…` menu, after its actions and shown with them; it gets the
   * tab index the actions have (0 on the selected row, else -1).
   */
  menu?: (tabIndex: number) => ReactNode;
  dense?: boolean;
}) {
  const list = useContext(ListContext);
  const selected = list?.activeId === id;
  const checked = list?.selection?.ids.has(id) ?? false;
  const gesture = useSwipe(swipe, onLongPress);
  const body = (
    <>
      <span className="ui-row-lead">
        {checked ? <Icon icon={Check} size="sm" /> : leading}
      </span>
      <span className="ui-row-text">
        <span className="ui-row-title">{title}</span>
        {sub && <span className="ui-row-sub">{sub}</span>}
      </span>
      {checked && <span className="ui-sr">, selected</span>}
    </>
  );
  function onClick(event: MouseEvent<HTMLElement>) {
    // A swipe or a long press already acted: no click after it.
    if (gesture.pressed.current) {
      gesture.pressed.current = false;
      event.preventDefault();
      return;
    }
    const selection = list?.selection;
    if (selection && event.shiftKey) {
      event.preventDefault();
      selection.extend(rowIds(event.currentTarget), id);
      return;
    }
    if (selection && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      selection.toggle(id);
      return;
    }
    list?.onActiveChange(id);
  }
  const common = {
    className: "ui-row-main",
    "data-row-id": id,
    tabIndex: list ? (selected ? 0 : -1) : 0,
    "aria-current": selected ? ("true" as const) : undefined,
    onClick,
  };
  const side =
    gesture.dx > 0 ? swipe?.right : gesture.dx < 0 ? swipe?.left : null;
  return (
    <li
      className="ui-row"
      data-selected={selected || undefined}
      data-checked={checked || undefined}
      data-dense={dense || undefined}
      data-has-actions={actions.length || menu ? "" : undefined}
      data-swipe={swipe ? "" : undefined}
      data-swiping={gesture.dx ? "" : undefined}
      style={
        gesture.dx
          ? ({ "--ui-swipe": `${gesture.dx}px` } as CSSProperties)
          : undefined
      }
      {...gesture.handlers}
    >
      {side && (
        <span
          className="ui-row-swipe"
          data-side={gesture.dx > 0 ? "right" : "left"}
          aria-hidden="true"
        >
          <Icon icon={side.icon} />
          {side.label}
        </span>
      )}
      {href ? (
        <a href={href} {...common}>
          {body}
        </a>
      ) : (
        <button type="button" {...common}>
          {body}
        </button>
      )}
      {(meta || actions.length > 0 || menu) && (
        <span className="ui-row-end">
          {meta && <span className="ui-row-meta">{meta}</span>}
          {(actions.length > 0 || menu) && (
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
              {menu?.(selected ? 0 : -1)}
            </span>
          )}
        </span>
      )}
    </li>
  );
}

/**
 * The bar that replaces the toolbar while rows are selected: the count, the
 * bulk actions and Clear (Esc).
 */
export function BulkBar({
  count,
  onClear,
  children,
}: {
  count: number;
  onClear: () => void;
  children: ReactNode;
}) {
  return (
    <div className="ui-bulkbar" role="toolbar" aria-label={`${count} selected`}>
      <span className="ui-bulkbar-count" aria-live="polite">
        {count} selected
      </span>
      <div className="ui-bulkbar-actions">{children}</div>
      <span className="ui-toolbar-spacer" />
      <Button variant="ghost" size="sm" kbd="Esc" onClick={onClear}>
        Clear
      </Button>
    </div>
  );
}
