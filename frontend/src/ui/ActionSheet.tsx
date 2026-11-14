import {
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Kbd } from "./Button";
import { Icon } from "./Icon";
import { cycleIndex } from "./keys";
import { Menu, type MenuEntry, type MenuItem, type TriggerProps } from "./Menu";
import "./actionsheet.css";

const PHONE = "(max-width: 719px)";

/** Whether the viewport is a phone's (under 720 px); follows resizes. */
export function usePhone() {
  return useSyncExternalStore(
    (listener) => {
      const query = window.matchMedia(PHONE);
      query.addEventListener("change", listener);
      return () => query.removeEventListener("change", listener);
    },
    () => window.matchMedia(PHONE).matches,
    () => false,
  );
}

/**
 * A `…` menu that is a popover menu on wide screens and a bottom sheet on a
 * phone, inside the safe area with 44 px items. Same items as Menu: groups
 * with a heading, separators, destructive items last and red.
 */
export function SheetMenu({
  label,
  trigger,
  items,
  placement = "bottom-end",
}: {
  label: string;
  trigger: (props: TriggerProps) => ReactNode;
  items: MenuEntry[];
  placement?: "bottom-start" | "bottom-end" | "top-start" | "top-end";
}) {
  const phone = usePhone();
  if (!phone)
    return (
      <Menu
        label={label}
        trigger={trigger}
        items={items}
        placement={placement}
      />
    );
  return <Sheet label={label} trigger={trigger} items={items} />;
}

function Sheet({
  label,
  trigger,
  items,
}: {
  label: string;
  trigger: (props: TriggerProps) => ReactNode;
  items: MenuEntry[];
}) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) {
      el.showModal();
      el.querySelector<HTMLElement>(".ui-menu-item")?.focus();
    } else if (!open && el.open) el.close();
  }, [open]);
  const close = () => {
    setOpen(false);
    button.current?.focus();
  };
  const choose = (item: MenuItem) => {
    if (item.disabled) return;
    close();
    item.onSelect?.();
  };
  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    const buttons = [
      ...event.currentTarget.querySelectorAll<HTMLElement>(
        ".ui-menu-item:not([aria-disabled])",
      ),
    ];
    const next = cycleIndex(
      event.key,
      buttons.indexOf(document.activeElement as HTMLElement),
      buttons.length,
    );
    if (next == null) return;
    event.preventDefault();
    buttons[next]?.focus();
  }
  const row = (item: MenuItem) => (
    <button
      key={item.id}
      type="button"
      role="menuitem"
      tabIndex={-1}
      className="ui-menu-item"
      data-danger={item.danger || undefined}
      aria-disabled={item.disabled || undefined}
      onClick={() => choose(item)}
    >
      {item.icon && <Icon icon={item.icon} />}
      <span className="ui-menu-label">{item.label}</span>
      {item.kbd && <Kbd>{item.kbd}</Kbd>}
    </button>
  );
  return (
    <>
      {trigger({
        ref: button,
        "aria-haspopup": "menu",
        "aria-expanded": open,
        "aria-controls": id,
        onClick: () => setOpen((value) => !value),
        onKeyDown: () => undefined,
      })}
      <dialog
        ref={dialog}
        id={id}
        className="ui-sheet"
        aria-label={label}
        onCancel={(event) => {
          event.preventDefault();
          close();
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget) close();
        }}
      >
        {open && (
          <div
            role="menu"
            aria-label={label}
            className="ui-sheet-menu"
            onKeyDown={onKeyDown}
          >
            <span className="ui-sheet-grip" aria-hidden="true" />
            {items.map((entry, index) =>
              entry === "separator" ? (
                <hr key={`sep-${index}`} className="ui-menu-sep" />
              ) : "id" in entry ? (
                row(entry)
              ) : (
                <div
                  key={entry.heading}
                  role="group"
                  aria-labelledby={`${id}-${index}`}
                >
                  <p id={`${id}-${index}`} className="ui-menu-heading">
                    {entry.heading}
                  </p>
                  {entry.items.map(row)}
                </div>
              ),
            )}
            <hr className="ui-menu-sep" />
            <button
              type="button"
              role="menuitem"
              tabIndex={-1}
              className="ui-menu-item ui-sheet-cancel"
              onClick={close}
            >
              <span className="ui-menu-label">Cancel</span>
            </button>
          </div>
        )}
      </dialog>
    </>
  );
}
