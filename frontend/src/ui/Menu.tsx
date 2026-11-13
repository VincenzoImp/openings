import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { Check } from "lucide-react";
import { Kbd } from "./Button";
import { cx } from "./cx";
import { Icon, type LucideIcon } from "./Icon";
import { cycleIndex, typeahead } from "./keys";
import "./menu.css";

export interface MenuItem {
  id: string;
  label: string;
  icon?: LucideIcon;
  kbd?: string;
  /** Destructive: red, and placed last after a separator. */
  danger?: boolean;
  /** A choice among several (radio) or an on/off item (checkbox). */
  kind?: "radio" | "checkbox";
  checked?: boolean;
  disabled?: boolean;
  onSelect?: () => void;
}
export interface MenuGroup {
  heading: string;
  items: MenuItem[];
}
export type MenuEntry = MenuItem | MenuGroup | "separator";

const isItem = (entry: MenuEntry): entry is MenuItem =>
  typeof entry === "object" && "id" in entry;

type Placement = "bottom-start" | "bottom-end" | "top-start" | "top-end";

/**
 * Places a popover next to its trigger, inside the viewport: below by
 * default, above when it does not fit, aligned to the trigger's start or end.
 */
function place(
  popover: HTMLElement,
  trigger: HTMLElement,
  placement: Placement,
) {
  const anchor = trigger.getBoundingClientRect();
  const { width, height } = popover.getBoundingClientRect();
  const gap = 4,
    edge = 8;
  const vw = document.documentElement.clientWidth,
    vh = window.innerHeight;
  let top =
    placement.startsWith("top") ? anchor.top - height - gap : anchor.bottom + gap;
  if (top + height > vh - edge && anchor.top - height - gap >= edge)
    top = anchor.top - height - gap;
  if (top < edge && anchor.bottom + gap + height <= vh - edge)
    top = anchor.bottom + gap;
  let left = placement.endsWith("end") ? anchor.right - width : anchor.left;
  left = Math.max(edge, Math.min(left, vw - width - edge));
  popover.style.top = `${Math.max(edge, top)}px`;
  popover.style.left = `${left}px`;
}

export interface TriggerProps {
  ref: RefObject<HTMLButtonElement | null>;
  "aria-haspopup": "menu" | "dialog";
  "aria-expanded": boolean;
  "aria-controls": string;
  onClick: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
}

/** Opening, closing and placing a native popover from a trigger. */
function usePopover(placement: Placement) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const focusOnOpen = useRef<"first" | "last" | "none">("first");

  const show = useCallback((focus: "first" | "last" | "none" = "first") => {
    const el = popover.current;
    if (!el || el.matches(":popover-open")) return;
    focusOnOpen.current = focus;
    el.showPopover();
  }, []);
  const hide = useCallback((returnFocus = true) => {
    const el = popover.current;
    if (el?.matches(":popover-open")) el.hidePopover();
    if (returnFocus) trigger.current?.focus();
  }, []);

  useEffect(() => {
    const el = popover.current;
    if (!el) return;
    const onToggle = (event: Event) => {
      const next = (event as ToggleEvent).newState === "open";
      setOpen(next);
      if (!next) {
        // Light dismiss (Esc, outside click) leaves focus nowhere useful.
        const active = document.activeElement;
        if (!active || active === document.body || el.contains(active))
          trigger.current?.focus();
      }
    };
    el.addEventListener("toggle", onToggle);
    return () => el.removeEventListener("toggle", onToggle);
  }, []);

  useLayoutEffect(() => {
    if (!open || !popover.current || !trigger.current) return;
    place(popover.current, trigger.current, placement);
    const close = () => hide(false);
    window.addEventListener("resize", close);
    return () => window.removeEventListener("resize", close);
  }, [open, placement, hide]);

  return { id, trigger, popover, open, show, hide, focusOnOpen };
}

function MenuButton({
  item,
  highlight,
  onSelect,
}: {
  item: MenuItem;
  highlight?: string;
  onSelect: (item: MenuItem) => void;
}) {
  const role =
    item.kind === "radio"
      ? "menuitemradio"
      : item.kind === "checkbox"
        ? "menuitemcheckbox"
        : "menuitem";
  return (
    <button
      type="button"
      role={role}
      tabIndex={-1}
      className="ui-menu-item"
      data-danger={item.danger || undefined}
      data-highlight={item.id === highlight || undefined}
      aria-checked={item.kind ? Boolean(item.checked) : undefined}
      aria-disabled={item.disabled || undefined}
      aria-keyshortcuts={item.kbd}
      onClick={() => !item.disabled && onSelect(item)}
    >
      {item.kind ? (
        <span className="ui-menu-check">
          {item.checked && <Icon icon={Check} size="sm" />}
        </span>
      ) : (
        item.icon && <Icon icon={item.icon} />
      )}
      <span className="ui-menu-label">{item.label}</span>
      {item.kind && item.icon && <Icon icon={item.icon} />}
      {item.kbd && <Kbd>{item.kbd}</Kbd>}
    </button>
  );
}

/** The items of a menu, shared by the live menu and its static preview. */
function MenuItems({
  entries,
  highlight,
  onSelect,
}: {
  entries: MenuEntry[];
  highlight?: string;
  onSelect: (item: MenuItem) => void;
}) {
  const base = useId();
  return entries.map((entry, index) => {
    if (entry === "separator")
      return <hr key={`sep-${index}`} className="ui-menu-sep" />;
    if (!isItem(entry))
      return (
        <div
          key={`group-${entry.heading}`}
          role="group"
          aria-labelledby={`${base}-${index}`}
        >
          <p id={`${base}-${index}`} className="ui-menu-heading">
            {entry.heading}
          </p>
          {entry.items.map((item) => (
            <MenuButton
              key={item.id}
              item={item}
              highlight={highlight}
              onSelect={onSelect}
            />
          ))}
        </div>
      );
    return (
      <MenuButton
        key={entry.id}
        item={entry}
        highlight={highlight}
        onSelect={onSelect}
      />
    );
  });
}

/** Arrow keys, Home, End and typeahead among a menu's items. */
function menuKeys(
  event: KeyboardEvent<HTMLElement>,
  close: () => void,
) {
  const items = [
    ...event.currentTarget.querySelectorAll<HTMLElement>(
      ".ui-menu-item:not([aria-disabled])",
    ),
  ];
  const current = items.indexOf(document.activeElement as HTMLElement);
  if (event.key === "Tab") {
    close();
    return;
  }
  let next = cycleIndex(event.key, current, items.length);
  if (next == null && event.key.length === 1 && /\S/.test(event.key))
    next = typeahead(
      items.map((item) => item.textContent || ""),
      event.key,
      current,
    );
  if (next == null || next < 0) return;
  event.preventDefault();
  items[next]?.focus();
}

/**
 * A menu opened from a trigger (`…` on a row, a toolbar button, the account
 * row): 220–260 px, icon, label and shortcut per item, separators between
 * groups, destructive items last and red. Arrow keys, typeahead and Esc;
 * focus returns to the trigger.
 */
export function Menu({
  label,
  trigger,
  items,
  placement = "bottom-start",
  className,
}: {
  label: string;
  trigger: (props: TriggerProps) => ReactNode;
  items: MenuEntry[];
  placement?: Placement;
  className?: string;
}) {
  const pop = usePopover(placement);
  useLayoutEffect(() => {
    if (!pop.open) return;
    const items = pop.popover.current?.querySelectorAll<HTMLElement>(
      ".ui-menu-item:not([aria-disabled])",
    );
    if (!items?.length) return;
    if (pop.focusOnOpen.current === "first") items[0].focus();
    if (pop.focusOnOpen.current === "last") items[items.length - 1].focus();
  }, [pop.open, pop.focusOnOpen, pop.popover]);

  return (
    <>
      {trigger({
        ref: pop.trigger,
        "aria-haspopup": "menu",
        "aria-expanded": pop.open,
        "aria-controls": pop.id,
        onClick: () => (pop.open ? pop.hide() : pop.show("first")),
        onKeyDown: (event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            pop.show(event.key === "ArrowDown" ? "first" : "last");
          }
        },
      })}
      <div
        ref={pop.popover}
        id={pop.id}
        popover="auto"
        role="menu"
        aria-label={label}
        className={cx("ui-menu ui-popover", className)}
        onKeyDown={(event) => menuKeys(event, () => pop.hide())}
      >
        <MenuItems
          entries={items}
          onSelect={(item) => {
            pop.hide();
            item.onSelect?.();
          }}
        />
      </div>
    </>
  );
}

/** A menu drawn in place, for documentation and previews. */
export function MenuPreview({
  label,
  items,
  highlight,
}: {
  label: string;
  items: MenuEntry[];
  highlight?: string;
}) {
  return (
    <div
      role="menu"
      aria-label={label}
      className="ui-menu"
      data-static=""
      onKeyDown={(event) => menuKeys(event, () => undefined)}
    >
      <MenuItems
        entries={items}
        highlight={highlight}
        onSelect={() => undefined}
      />
    </div>
  );
}

/**
 * A non-modal popover with free content, such as a (?) explanation or a
 * small form. Light dismiss, Esc, and focus back to the trigger.
 */
export function Popover({
  label,
  trigger,
  children,
  placement = "bottom-start",
}: {
  label: string;
  trigger: (props: TriggerProps) => ReactNode;
  children: ReactNode;
  placement?: Placement;
}) {
  const pop = usePopover(placement);
  return (
    <>
      {trigger({
        ref: pop.trigger,
        "aria-haspopup": "dialog",
        "aria-expanded": pop.open,
        "aria-controls": pop.id,
        onClick: () => (pop.open ? pop.hide() : pop.show("none")),
        onKeyDown: () => undefined,
      })}
      <div
        ref={pop.popover}
        id={pop.id}
        popover="auto"
        role="dialog"
        aria-label={label}
        className="ui-popover ui-popover-panel"
      >
        {children}
      </div>
    </>
  );
}
