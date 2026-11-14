import { useState, type ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { cx } from "./cx";
import { Icon } from "./Icon";
import "./disclosure.css";

/**
 * A section that starts collapsed (Recent checks, Advanced, More details): a
 * native <details> with a chevron, a heading-sized summary and an optional
 * count or note. The content is drawn only once it was opened.
 */
export function Disclosure({
  title,
  note,
  defaultOpen = false,
  onToggle,
  className,
  children,
}: {
  title: string;
  /** Beside the title, in text-3: a count or a short state. */
  note?: ReactNode;
  defaultOpen?: boolean;
  onToggle?: (open: boolean) => void;
  className?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details
      className={cx("ui-disclosure", className)}
      open={open}
      onToggle={(event) => {
        const next = event.currentTarget.open;
        setOpen(next);
        onToggle?.(next);
      }}
    >
      <summary className="ui-disclosure-summary">
        <Icon icon={ChevronRight} size="sm" className="ui-disclosure-chevron" />
        <span className="ui-disclosure-title">{title}</span>
        {note != null && <span className="ui-disclosure-note">{note}</span>}
      </summary>
      {open && <div className="ui-disclosure-body">{children}</div>}
    </details>
  );
}
