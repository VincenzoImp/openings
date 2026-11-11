import { cx } from "./classes";

/** A short confirmation or error. An error interrupts; a confirmation does not. */
export function Toast({
  message,
  error = false,
  inDialog = false,
  onDismiss,
}: {
  message: string;
  error?: boolean;
  /** The copy shown inside an open dialog, which covers the page's toast. */
  inDialog?: boolean;
  onDismiss: () => void;
}) {
  return (
    <div
      className={cx(
        "toast app-toast",
        inDialog && "dialog-toast",
        error && "error",
      )}
      role={error ? "alert" : "status"}
    >
      <span className="grow">{message}</span>
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={onDismiss}
      >
        ×
      </button>
    </div>
  );
}
