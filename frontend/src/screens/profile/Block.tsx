// One block of the CV in its two modes. At rest it is text, with Edit (and a
// `…` menu) on hover or focus; Edit turns it into its form in place, or into
// a full-screen sheet on a phone. One block is open at a time: opening
// another, cancelling or leaving the page with unsaved changes asks first,
// in an in-app dialog.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { MoreHorizontal, Pencil } from "lucide-react";
import { Button, IconButton } from "../../ui/Button";
import { usePhone } from "../../ui/ActionSheet";
import { Menu, type MenuEntry } from "../../ui/Menu";
import { LeaveDialog, SaveBar, useUnloadGuard } from "../../ui/ReadEdit";
import { isModKey } from "../../ui/keys";
import { addLeaveGuard } from "../../shell/router";

interface Editing {
  /** The open block, or null. */
  open: string | null;
  /** Open a block (null closes), asking first when there are changes. */
  request: (id: string | null) => void;
  /** Close without asking (after a save, or a discard already confirmed). */
  close: () => void;
  /** The open block's count of unsaved changes. */
  report: (changes: number) => void;
}
const EditingContext = createContext<Editing | null>(null);

export function useEditing() {
  const value = useContext(EditingContext);
  if (!value) throw Error("useEditing needs EditingProvider.");
  return value;
}

/** The one open block of the page, its changes and the questions before leaving. */
export function EditingProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState<string | null>(null);
  const [changes, setChanges] = useState(0);
  const [asking, setAsking] = useState<null | { then: () => void }>(null);
  const dirty = open !== null && changes > 0;
  useUnloadGuard(dirty);

  useEffect(() => {
    if (!dirty) return;
    return addLeaveGuard((proceed) => {
      setAsking({
        then: () => {
          setOpen(null);
          setChanges(0);
          proceed();
        },
      });
      return false;
    });
  }, [dirty]);

  const request = useCallback(
    (id: string | null) => {
      const go = () => {
        setOpen(id);
        setChanges(0);
      };
      if (dirty && id !== open) setAsking({ then: go });
      else go();
    },
    [dirty, open],
  );
  const value = useMemo<Editing>(
    () => ({
      open,
      request,
      close: () => {
        setOpen(null);
        setChanges(0);
      },
      report: setChanges,
    }),
    [open, request],
  );
  return (
    <EditingContext.Provider value={value}>
      {children}
      <LeaveDialog
        open={asking !== null}
        changes={changes}
        onStay={() => setAsking(null)}
        onLeave={() => {
          const next = asking;
          setAsking(null);
          next?.then();
        }}
      />
    </EditingContext.Provider>
  );
}

/** The read view of a block: content, and Edit and `…` on intent. */
export function ReadBlock({
  name,
  onEdit,
  menu,
  className,
  children,
}: {
  /** What Edit opens, for its accessible name: "Edit Senior data engineer". */
  name: string;
  onEdit: () => void;
  menu?: MenuEntry[];
  className?: string;
  children: ReactNode;
}) {
  return (
    // Focusable by a tap, so a phone shows the block's actions on intent.
    <div className={`pf-block ${className ?? ""}`} tabIndex={-1}>
      {children}
      <div className="pf-block-actions">
        <Button
          variant="ghost"
          size="sm"
          icon={Pencil}
          aria-label={`Edit ${name}`}
          onClick={onEdit}
        >
          Edit
        </Button>
        {menu && (
          <Menu
            label={`More actions for ${name}`}
            placement="bottom-end"
            items={menu}
            trigger={(props) => (
              <IconButton
                {...props}
                icon={MoreHorizontal}
                size="sm"
                label={`More actions for ${name}`}
                tooltip="none"
              />
            )}
          />
        )}
      </div>
    </div>
  );
}

/**
 * The form of an open block: in place on wide screens with the sticky save
 * bar while dirty; a full-screen sheet with Cancel and Save in its header on
 * a phone. ⌘↵ saves, Esc cancels (asking when there are changes).
 */
export function EditBlock({
  title,
  changes,
  saving,
  notice,
  onSave,
  className,
  children,
}: {
  /** The sheet's title on a phone, and the form's name. */
  title: string;
  changes: number;
  saving: boolean;
  /** A conflict or an error, above the fields. */
  notice?: ReactNode;
  /** Save the draft; the block closes when it resolves to true. */
  onSave: () => Promise<boolean>;
  className?: string;
  children: ReactNode;
}) {
  const editing = useEditing();
  const phone = usePhone();
  const id = useId();
  const formId = `${id}-form`;
  const sheet = useRef<HTMLDialogElement>(null);
  const first = useRef(true);

  useEffect(() => editing.report(changes), [changes, editing]);

  const save = async () => {
    if (saving) return;
    if (await onSave()) editing.close();
  };
  const cancel = () => editing.request(null);

  // The first field takes focus when the block opens.
  const formRef = useCallback((form: HTMLFormElement | null) => {
    if (!form || !first.current) return;
    first.current = false;
    requestAnimationFrame(() =>
      form
        .querySelector<HTMLElement>("input:not([type=file]), textarea, select")
        ?.focus(),
    );
  }, []);

  useEffect(() => {
    const dialog = sheet.current;
    if (phone && dialog && !dialog.open) dialog.showModal();
  }, [phone]);

  const form = (
    <form
      ref={formRef}
      id={formId}
      aria-label={title}
      className={`pf-form ${className ?? ""}`}
      noValidate
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        void save();
      }}
      onKeyDown={(event: KeyboardEvent) => {
        if (event.key === "Enter" && isModKey(event.nativeEvent)) {
          event.preventDefault();
          void save();
        } else if (
          event.key === "Escape" &&
          !event.defaultPrevented &&
          !document.querySelector(":popover-open")
        ) {
          event.preventDefault();
          event.stopPropagation();
          cancel();
        }
      }}
    >
      {notice}
      {children}
    </form>
  );

  if (phone)
    return (
      <dialog
        ref={sheet}
        className="pf-sheet"
        aria-labelledby={`${id}-title`}
        onCancel={(event) => {
          event.preventDefault();
          cancel();
        }}
      >
        <header className="pf-sheet-head">
          <Button variant="ghost" size="touch" onClick={cancel}>
            Cancel
          </Button>
          <h2 id={`${id}-title`}>{title}</h2>
          <Button
            variant="primary"
            size="touch"
            type="submit"
            form={formId}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </header>
        <div className="pf-sheet-body">{form}</div>
      </dialog>
    );

  return (
    <div className="pf-editing">
      {form}
      {changes > 0 ? (
        <SaveBar
          changes={changes}
          saving={saving}
          onCancel={cancel}
          form={formId}
        />
      ) : (
        <div className="pf-editing-idle">
          <Button variant="ghost" onClick={cancel}>
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
