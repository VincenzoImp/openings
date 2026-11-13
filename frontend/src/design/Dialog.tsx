import { useEffect, useId, useRef, type ReactNode } from "react";
import { Notification, confirmLeave, useWorkspace } from "../state";
import { IconButton } from "./Button";
import { cx } from "./classes";

let scrollLocks = 0;
let originalOverflow = "";
/** Stop the page behind an overlay from scrolling; returns the release. */
export function lockPageScroll() {
  if (scrollLocks++ === 0) {
    originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
  }
  let released = false;
  return () => {
    if (released) return;
    released = true;
    if (--scrollLocks === 0) document.body.style.overflow = originalOverflow;
  };
}

/**
 * A modal dialog. The browser keeps focus
 * inside it; closing asks before discarding unsaved edits and returns focus
 * to the control that opened it.
 */
export function Dialog({
  title,
  children,
  onClose,
  footer,
  className,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null),
    id = useId();
  const { dismiss } = useWorkspace();
  const close = () => {
    if (!ref.current || confirmLeave(ref.current)) onClose();
  };
  useEffect(() => {
    const last = document.activeElement as HTMLElement | null;
    // A notification from before the dialog is not about it.
    dismiss();
    ref.current?.showModal();
    const unlock = lockPageScroll();
    return () => {
      unlock();
      if (last?.isConnected) last.focus({ preventScroll: true });
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={cx("dialog", className)}
      aria-labelledby={id}
      onCancel={(event) => {
        event.preventDefault();
        event.stopPropagation();
        close();
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const box = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < box.left ||
          event.clientX > box.right ||
          event.clientY < box.top ||
          event.clientY > box.bottom
        )
          close();
      }}
    >
      <div className="dialog-head">
        <IconButton
          icon="close"
          label="Close dialog"
          className="close"
          onClick={close}
        />
        <h2 id={id}>{title}</h2>
      </div>
      <div className="dialog-body">{children}</div>
      {footer && <div className="dialog-foot">{footer}</div>}
      <Notification inDialog />
    </dialog>
  );
}
