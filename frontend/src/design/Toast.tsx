import { useEffect, useState } from "react";
import { cx } from "./classes";

/** How long a confirmation stays, unless the pointer or focus is on it. */
export const TOAST_MS = 6000;

/**
 * A short confirmation or error. A confirmation goes by itself after six
 * seconds, waiting while the pointer or focus is on it; an error stays until
 * it is closed. An action (Undo) runs once and closes the toast.
 */
export function Toast({
  message,
  error = false,
  action,
  inDialog = false,
  onDismiss,
}: {
  message: string;
  error?: boolean;
  action?: { label: string; run: () => void };
  /** The copy shown by an open dialog, which covers the page's toast. */
  inDialog?: boolean;
  onDismiss: () => void;
}) {
  const [hovered, setHovered] = useState(false),
    [focused, setFocused] = useState(false);
  const held = hovered || focused;
  useEffect(() => {
    if (error || held) return;
    const timer = setTimeout(onDismiss, TOAST_MS);
    return () => clearTimeout(timer);
  }, [error, held, onDismiss]);
  return (
    <div
      className={cx(
        "toast app-toast",
        inDialog && "dialog-toast",
        error && "error",
      )}
      role={error ? "alert" : "status"}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          setFocused(false);
      }}
    >
      <span className="grow">{message}</span>
      {action && (
        <button
          type="button"
          className="toast-action"
          onClick={() => {
            onDismiss();
            action.run();
          }}
        >
          {action.label}
        </button>
      )}
      <button
        type="button"
        className="toast-close"
        aria-label="Dismiss notification"
        onClick={onDismiss}
      >
        ×
      </button>
    </div>
  );
}
