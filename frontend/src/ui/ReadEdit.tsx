import {
  useEffect,
  useId,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { Pencil } from "lucide-react";
import { Button } from "./Button";
import { ConfirmDialog } from "./Dialog";
import { isModKey } from "./keys";
import "./readedit.css";

/**
 * The sticky bar of a dirty form: "● N unsaved changes", then Cancel (ghost)
 * and Save (primary, ⌘↵). It exists only while there are changes.
 */
export function SaveBar({
  changes,
  saving = false,
  onCancel,
  form,
}: {
  changes: number;
  saving?: boolean;
  onCancel: () => void;
  /** The id of the form Save submits. */
  form?: string;
}) {
  if (changes <= 0) return null;
  return (
    <div className="ui-savebar" role="region" aria-label="Unsaved changes">
      <span className="ui-savebar-note" aria-live="polite">
        <span className="ui-savebar-dot" aria-hidden="true" />
        {changes === 1 ? "1 unsaved change" : `${changes} unsaved changes`}
      </span>
      <span className="ui-savebar-spacer" />
      <Button variant="ghost" onClick={onCancel} disabled={saving}>
        Cancel
      </Button>
      <Button
        variant="primary"
        type="submit"
        form={form}
        kbd="⌘↵"
        disabled={saving}
        aria-keyshortcuts="Meta+Enter Control+Enter"
      >
        {saving ? "Saving…" : "Save"}
      </Button>
    </div>
  );
}

/** Asks before the page unloads while there are unsaved changes. */
export function useUnloadGuard(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const onUnload = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, [dirty]);
}

/** The in-app question before leaving unsaved changes; never window.confirm. */
export function LeaveDialog({
  open,
  changes,
  onStay,
  onLeave,
}: {
  open: boolean;
  changes: number;
  onStay: () => void;
  onLeave: () => void;
}) {
  return (
    <ConfirmDialog
      open={open}
      title="Discard unsaved changes?"
      confirm="Discard"
      cancel="Keep editing"
      onConfirm={onLeave}
      onClose={onStay}
    >
      {changes === 1
        ? "You have 1 unsaved change. Discarding it cannot be undone."
        : `You have ${changes} unsaved changes. Discarding them cannot be undone.`}
    </ConfirmDialog>
  );
}

/**
 * Read first, edit on purpose. A record renders as text with an Edit button;
 * Edit turns the block into its form in place, with the save bar while it is
 * dirty. ⌘↵ saves; Cancel with changes asks before discarding them, and the
 * page asks before unloading them.
 */
export function ReadEdit({
  title,
  editing,
  onEdit,
  read,
  form,
  changes,
  saving,
  onSave,
  onDiscard,
}: {
  title: ReactNode;
  editing: boolean;
  onEdit: () => void;
  read: ReactNode;
  form: ReactNode;
  changes: number;
  saving?: boolean;
  onSave: () => void;
  /** Leaves edit mode, dropping the draft. */
  onDiscard: () => void;
}) {
  const id = useId();
  const [asking, setAsking] = useState(false);
  useUnloadGuard(editing && changes > 0);
  const cancel = () => (changes > 0 ? setAsking(true) : onDiscard());
  const save = () => {
    if (changes > 0 && !saving) onSave();
  };
  return (
    <section className="ui-readedit" aria-labelledby={`${id}-title`}>
      <header className="ui-readedit-head">
        <h2 id={`${id}-title`}>{title}</h2>
        {!editing && (
          <Button variant="ghost" size="sm" icon={Pencil} onClick={onEdit}>
            Edit
          </Button>
        )}
      </header>
      {editing ? (
        <form
          id={`${id}-form`}
          className="ui-readedit-form"
          noValidate
          data-unguarded=""
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            save();
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && isModKey(event.nativeEvent)) {
              event.preventDefault();
              save();
            }
            if (event.key === "Escape") {
              event.preventDefault();
              cancel();
            }
          }}
        >
          <div className="ui-readedit-fields">{form}</div>
          {changes > 0 ? (
            <SaveBar
              changes={changes}
              saving={saving}
              onCancel={cancel}
              form={`${id}-form`}
            />
          ) : (
            <div className="ui-readedit-idle">
              <Button variant="ghost" onClick={onDiscard}>
                Done
              </Button>
            </div>
          )}
        </form>
      ) : (
        <div className="ui-readedit-read">{read}</div>
      )}
      <LeaveDialog
        open={asking}
        changes={changes}
        onStay={() => setAsking(false)}
        onLeave={() => {
          setAsking(false);
          onDiscard();
        }}
      />
    </section>
  );
}
