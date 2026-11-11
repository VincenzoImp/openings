// Components for the pages written before the design system. Buttons, tabs,
// fields, dialogs and feedback come from ./design; this module keeps the older
// names and loads the stylesheet those pages still need. A rebuilt page imports
// from ./design instead.
import { useState, type ReactNode } from "react";
import { Button, EmptyState, ErrorBanner, Field } from "./design";
import "./legacy.css";

export {
  Button,
  Dialog,
  Field,
  Icon,
  Loading,
  Switch,
  Tabs,
  lockPageScroll,
  type IconName,
} from "./design";
export const Empty = EmptyState;
export const ErrorBox = ErrorBanner;

export function Heading({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-head spread">
      <div className="grow">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children && <div className="row">{children}</div>}
    </header>
  );
}
export function LazyDetails({
  summary,
  className,
  children,
}: {
  summary: string;
  className?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className={className}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>{summary}</summary>
      {open && children}
    </details>
  );
}
export function PendingResults({ pending }: { pending: boolean }) {
  return pending ? (
    <p className="loading inline-loading" role="status">
      <span className="spinner" />
      Updating results…
    </p>
  ) : null;
}
export const stageLabels = {
  draft: "Preparing",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
};
export const outcomeLabels: Record<string, string> = {
  accepted: "Accepted",
  rejected: "Not selected",
  not_pursued: "Not pursued",
};
export function outcomeLabel(outcome?: string | null) {
  return (outcome && outcomeLabels[outcome]) || "—";
}

export function AdvancedJson({
  name,
  label = "Metadata",
  value = {},
  array = false,
}: {
  name: string;
  label?: string;
  value?: unknown;
  array?: boolean;
}) {
  return (
    <details className="advanced-json">
      <summary>Advanced · {label}</summary>
      <Field
        label={`${label} JSON`}
        hint={
          array
            ? "A JSON array. Existing custom values are preserved."
            : "A JSON object. Existing custom values are preserved."
        }
      >
        <textarea
          className="source-editor"
          name={name}
          rows={5}
          defaultValue={JSON.stringify(value, null, 2)}
          onChange={(event) => {
            try {
              const parsed = JSON.parse(event.target.value);
              if (
                array
                  ? !Array.isArray(parsed)
                  : typeof parsed !== "object" ||
                    parsed === null ||
                    Array.isArray(parsed)
              )
                throw Error();
              event.target.setCustomValidity("");
            } catch {
              event.target.setCustomValidity(
                `Enter a valid JSON ${array ? "array" : "object"}.`,
              );
            }
          }}
        />
      </Field>
    </details>
  );
}
export function Pagination({
  offset,
  total,
  limit = 30,
  onChange,
  label = "Result pages",
}: {
  offset: number;
  total: number;
  limit?: number;
  onChange: (value: number) => void;
  label?: string;
}) {
  return (
    <div className="list-footer" role="navigation" aria-label={label}>
      <span>
        {total
          ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}`
          : "0 results"}
      </span>
      <div className="actions">
        <Button
          type="button"
          className="small"
          disabled={!offset}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Previous
        </Button>
        <Button
          type="button"
          className="small"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
