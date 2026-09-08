import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

import { useHotkeys } from "../app/hotkeys";
import { Button } from "./Button";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Dialog({
  open,
  title,
  onClose,
  children,
  footer,
  wide = false,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const restoreTo = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useHotkeys("dialog", [{ key: "Escape", run: onClose }], open);

  useEffect(() => {
    if (!open) {
      return;
    }
    restoreTo.current = document.activeElement as HTMLElement | null;
    const node = panel.current;
    const preferred = node?.querySelector<HTMLElement>("[autofocus]");
    const first = preferred ?? node?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab" || !node) {
        return;
      }
      const focusable = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusable.length === 0) {
        return;
      }
      const start = focusable[0];
      const end = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === start) {
        event.preventDefault();
        end.focus();
      } else if (!event.shiftKey && document.activeElement === end) {
        event.preventDefault();
        start.focus();
      }
    };
    window.addEventListener("keydown", trap);
    return () => {
      window.removeEventListener("keydown", trap);
      document.body.style.overflow = previousOverflow;
      restoreTo.current?.focus?.();
    };
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center bg-black/50 p-0 sm:items-start sm:p-4 sm:pt-16"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`flex max-h-[calc(100dvh-1rem)] w-full flex-col rounded-t-lg border border-edge bg-surface shadow-panel sm:max-h-[calc(100dvh-5rem)] sm:rounded-lg ${wide ? "sm:max-w-3xl" : "sm:max-w-lg"}`}
        style={{ overscrollBehavior: "contain" }}
      >
        <div className="flex items-center justify-between gap-3 border-b border-edge px-4 py-3">
          <h2 id={titleId} className="truncate text-base font-semibold text-fg">
            {title}
          </h2>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
            <X size={16} aria-hidden="true" />
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">{children}</div>
        {footer ? (
          <div className="flex flex-wrap justify-end gap-2 border-t border-edge px-4 py-3">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
