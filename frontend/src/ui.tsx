import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useRef,
  type ReactNode,
  type ButtonHTMLAttributes,
} from "react";
import {
  LayoutDashboard,
  Inbox,
  BriefcaseBusiness,
  Building2,
  UserRound,
  Files,
  SlidersHorizontal,
  Plus,
  Search,
  X,
  Bookmark,
  Check,
  ArrowRight,
  Download,
  RefreshCw,
  Clock,
  FileText,
  Menu,
  Moon,
  Sun,
  Pencil,
  Columns3,
  List,
  Info,
  Copy,
  Trash2,
  Play,
  LogOut,
  Upload,
  ExternalLink,
  AlertCircle,
} from "lucide-react";
import { Notification, confirmLeave } from "./state";
const icons = {
  overview: LayoutDashboard,
  inbox: Inbox,
  applications: BriefcaseBusiness,
  companies: Building2,
  career: UserRound,
  templates: Files,
  settings: SlidersHorizontal,
  plus: Plus,
  search: Search,
  close: X,
  bookmark: Bookmark,
  check: Check,
  arrow: ArrowRight,
  download: Download,
  refresh: RefreshCw,
  clock: Clock,
  file: FileText,
  menu: Menu,
  moon: Moon,
  sun: Sun,
  edit: Pencil,
  board: Columns3,
  list: List,
  info: Info,
  copy: Copy,
  trash: Trash2,
  play: Play,
  logout: LogOut,
  upload: Upload,
  external: ExternalLink,
  error: AlertCircle,
};
export type IconName = keyof typeof icons;
export function Icon({ name }: { name: IconName }) {
  const I = icons[name];
  return <I className="icon" size={18} strokeWidth={1.5} aria-hidden="true" />;
}
export function Button({
  children,
  variant = "",
  icon,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: string;
  icon?: IconName;
}) {
  return (
    <button {...props} className={`btn ${variant} ${props.className || ""}`}>
      {icon && <Icon name={icon} />} {children}
    </button>
  );
}
export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  const control =
    isValidElement(children) &&
    typeof children.type === "string" &&
    ["input", "textarea", "select"].includes(children.type);
  const child = control
    ? cloneElement(children as React.ReactElement<Record<string, unknown>>, {
        id,
        "aria-describedby": hint ? id + "-hint" : undefined,
      })
    : children;
  return (
    <div className={`field ${className}`}>
      <label className="fieldlabel" htmlFor={control ? id : undefined}>
        {label}
      </label>
      {child}
      {hint && <small id={id + "-hint"}>{hint}</small>}
    </div>
  );
}
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
    <header className="pagehead">
      <div>
        <div className="eyebrow">Your workspace</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="actions">{children}</div>
    </header>
  );
}
export function Tabs({
  items,
  value,
  onChange,
  label,
}: {
  items: { id: string; label: string; count?: number }[];
  value: string;
  onChange: (id: string) => void;
  label: string;
}) {
  return (
    <div
      className="tabs"
      role="tablist"
      aria-label={label}
      onKeyDown={(event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
          return;
        event.preventDefault();
        const current = items.findIndex((item) => item.id === value);
        const next =
          event.key === "Home"
            ? 0
            : event.key === "End"
              ? items.length - 1
              : (current +
                  (event.key === "ArrowRight" ? 1 : -1) +
                  items.length) %
                items.length;
        if (!confirmLeave()) return;
        onChange(items[next].id);
        event.currentTarget
          .querySelectorAll<HTMLButtonElement>("[role=tab]")
          [next]?.focus();
      }}
    >
      {items.map((item) => (
        <button
          type="button"
          role="tab"
          aria-selected={item.id === value}
          tabIndex={item.id === value ? 0 : -1}
          className={`tab ${item.id === value ? "active" : ""}`}
          key={item.id}
          onClick={() => {
            if (item.id === value || confirmLeave()) onChange(item.id);
          }}
        >
          {item.label}
          {item.count !== undefined && (
            <span className="tabcount">{item.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <h2>{title}</h2>
      <p>{children}</p>
      {action && <div className="actions centered">{action}</div>}
    </div>
  );
}
export function ErrorBox({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="note error-note" role="alert">
      <Icon name="error" />
      <div>
        {message}
        {retry && (
          <button className="textbutton" onClick={retry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      Loading workspace…
    </div>
  );
}
export function Avatar({ name }: { name: string }) {
  const colors = ["#dce6d9", "#e5dfd5", "#dfddea", "#dce5e9", "#e6e4d8"];
  return (
    <span
      className="logo"
      style={{ background: colors[(name.charCodeAt(0) || 0) % colors.length] }}
      aria-hidden="true"
    >
      {name[0]?.toUpperCase() || "?"}
    </span>
  );
}
export function Score({
  score,
  outdated,
}: {
  score: number | null | undefined;
  outdated?: boolean;
}) {
  return (
    <span className="scorebox">
      {score == null ? (
        <span className="muted smalltext">Unscored</span>
      ) : (
        <>
          <span className="score">
            <i className={`dot ${score >= 75 ? "" : "offer"}`} />
            {Math.round(score)} <small>fit</small>
          </span>
          {outdated && <span className="tag amber">Outdated</span>}
        </>
      )}
    </span>
  );
}
export function Switch({
  label,
  checked,
  onChange,
  disabled = false,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      data-dirty-control="true"
      role="switch"
      className="switch"
      aria-label={label}
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
    />
  );
}
export function Dialog({
  title,
  children,
  onClose,
  drawer = false,
  footer,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  drawer?: boolean;
  footer?: ReactNode;
}) {
  const close = () => {
    if (!ref.current || confirmLeave(ref.current)) onClose();
  };
  const ref = useRef<HTMLDialogElement>(null),
    id = useId();
  useEffect(() => {
    const last = document.activeElement as HTMLElement | null;
    ref.current?.showModal();
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = old;
      last?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={drawer ? "drawer native-dialog" : "modal native-dialog"}
      aria-labelledby={id}
      onCancel={(e) => {
        e.preventDefault();
        e.stopPropagation();
        close();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          const r = e.currentTarget.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            close();
        }
      }}
    >
      <div className={drawer ? "drawerhead" : "modalhead"}>
        <button
          className="iconbtn close"
          aria-label="Close dialog"
          onClick={close}
        >
          <Icon name="close" />
        </button>
        <h2 id={id}>{title}</h2>
      </div>
      <div className={drawer ? "drawercontent" : "modalcontent"}>
        {children}
      </div>
      {footer && <div className="drawerfoot">{footer}</div>}
      <Notification inDialog />
    </dialog>
  );
}
export const stageLabels = {
  draft: "Draft",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
};

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
