// Small pieces the Library screens (Career, Preferences, Templates) share.
import type { ReactNode } from "react";
import { Button, Dialog, ErrorBanner, Loading } from "../design";
import { useTitle } from "../shell/context";
import { useWorkspace } from "../state";
import type { Fresh } from "./useFresh";

/**
 * The content of a card that reads a record: a loading line, the error with
 * a retry, or the content once the record is there.
 */
export function Loaded<T>({
  from,
  label,
  children,
}: {
  from: Fresh<T>;
  /** What is loading: "Loading runs…". */
  label: string;
  children: (data: T) => ReactNode;
}) {
  if (from.error)
    return (
      <div className="body">
        <ErrorBanner message={from.error} retry={from.reload} />
      </div>
    );
  if (from.loading) return <Loading label={label} />;
  return children(from.data);
}

export function PageHead({
  title,
  children,
  actions,
}: {
  title: string;
  /** One or two sentences that say what the screen holds. */
  children: ReactNode;
  actions?: ReactNode;
}) {
  // On a phone the shell's top bar shows this title instead of the h1.
  useTitle(title);
  return (
    <header className="page-head spread">
      <div className="grow">
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      {actions && <div className="row">{actions}</div>}
    </header>
  );
}

/** Asks before a removal; the button names what will happen. */
export function ConfirmDialog({
  title,
  confirm,
  keep,
  onConfirm,
  onClose,
  children,
}: {
  title: string;
  /** The destructive button: "Remove entry". */
  confirm: string;
  /** The safe button: "Keep entry". */
  keep: string;
  onConfirm: () => void | Promise<void>;
  onClose: () => void;
  children: ReactNode;
}) {
  const { pending } = useWorkspace();
  return (
    <Dialog
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>{keep}</Button>
          <Button variant="danger" disabled={pending} onClick={onConfirm}>
            {confirm}
          </Button>
        </>
      }
    >
      <div className="stack">{children}</div>
    </Dialog>
  );
}

/** Previous and next page of a list, with the range shown. */
export function Pager({
  offset,
  total,
  limit = 30,
  onChange,
  label = "Pages",
}: {
  offset: number;
  total: number;
  limit?: number;
  onChange: (offset: number) => void;
  label?: string;
}) {
  if (total <= limit && !offset) return null;
  return (
    <footer role="navigation" aria-label={label}>
      <span className="muted grow num">
        {total
          ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}`
          : "No results"}
      </span>
      <Button
        size="sm"
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - limit))}
      >
        Previous
      </Button>
      <Button
        size="sm"
        disabled={offset + limit >= total}
        onClick={() => onChange(offset + limit)}
      >
        Next
      </Button>
    </footer>
  );
}

export const plural = (count: number, one: string, many = one + "s") =>
  `${count} ${count === 1 ? one : many}`;

/** A file size in the unit a person would say. */
export function fileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
