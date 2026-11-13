import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { Button, IconButton } from "./Button";
import { cx } from "./cx";
import "./dialog.css";

/**
 * A native modal <dialog>: traps focus, closes on Esc, and returns focus to
 * what had it before. `kind="drawer"` slides in from the right, full height,
 * with a sticky header and footer.
 */
function Modal({
  open,
  onClose,
  title,
  description,
  footer,
  kind,
  dismissible = true,
  initialFocus,
  className,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  footer?: ReactNode;
  kind: "dialog" | "drawer";
  /** Whether a click on the backdrop closes it (Esc always does). */
  dismissible?: boolean;
  /** A selector, inside the dialog, of the element to focus first. */
  initialFocus?: string;
  className?: string;
  children?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);
  const id = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      returnTo.current = document.activeElement as HTMLElement | null;
      dialog.showModal();
      const first = initialFocus
        ? dialog.querySelector<HTMLElement>(initialFocus)
        : null;
      first?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open, initialFocus]);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const restore = () => {
      const target = returnTo.current;
      returnTo.current = null;
      if (target?.isConnected) target.focus();
    };
    dialog.addEventListener("close", restore);
    return () => dialog.removeEventListener("close", restore);
  }, []);

  return (
    <dialog
      ref={ref}
      className={cx("ui-modal", className)}
      data-kind={kind}
      aria-labelledby={`${id}-title`}
      aria-describedby={description ? `${id}-desc` : undefined}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (dismissible && event.target === event.currentTarget) onClose();
      }}
    >
      <div className="ui-modal-frame">
          <header className="ui-modal-head">
            <h2 id={`${id}-title`}>{title}</h2>
            {kind === "drawer" && (
              <IconButton
                icon={X}
                label="Close"
                shortcut="Esc"
                tooltip="none"
                onClick={onClose}
              />
            )}
          </header>
          <div className="ui-modal-body">
            {description && (
              <p className="ui-modal-desc" id={`${id}-desc`}>
                {description}
              </p>
            )}
            {children}
          </div>
          {footer && <footer className="ui-modal-foot">{footer}</footer>}
        </div>
    </dialog>
  );
}

type DialogProps = Omit<Parameters<typeof Modal>[0], "kind">;

/**
 * A dialog, at most 440 px: short creation (Add job), permanent deletion and
 * leaving without saving. Actions right-aligned, Cancel then the primary.
 * Reversible actions use an undo toast instead.
 */
export function Dialog(props: DialogProps) {
  return <Modal {...props} kind="dialog" />;
}

/** A right-side drawer, 480–640 px, for long records and narrow details. */
export function Drawer(props: DialogProps) {
  return <Modal {...props} kind="drawer" />;
}

/**
 * The confirmation of an irreversible action, the only place a danger
 * button appears at rest.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirm,
  cancel = "Cancel",
  danger = true,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirm: string;
  cancel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      description={children}
      dismissible={false}
      initialFocus="[data-autofocus]"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} data-autofocus="">
            {cancel}
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            onClick={() => {
              onConfirm();
              onClose();
            }}
          >
            {confirm}
          </Button>
        </>
      }
    />
  );
}

/** A dialog drawn in place over a backdrop, for documentation. */
export function DialogPreview({
  title,
  children,
  footer,
}: {
  title: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  const id = useId();
  return (
    <div className="ui-dialog-preview">
      <div
        className="ui-modal-frame"
        data-kind="dialog"
        role="dialog"
        aria-labelledby={`${id}-t`}
      >
        <header className="ui-modal-head">
          <h2 id={`${id}-t`}>{title}</h2>
        </header>
        <div className="ui-modal-body">
          <p className="ui-modal-desc">{children}</p>
        </div>
        <footer className="ui-modal-foot">{footer}</footer>
      </div>
    </div>
  );
}
