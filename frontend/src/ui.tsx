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
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          type="button"
          role="tab"
          aria-selected={item.id === value}
          className={`tab ${item.id === value ? "active" : ""}`}
          key={item.id}
          onClick={() => onChange(item.id)}
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
        onClose();
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
            onClose();
        }
      }}
    >
      <div className={drawer ? "drawerhead" : "modalhead"}>
        <button
          className="iconbtn close"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
        <h2 id={id}>{title}</h2>
      </div>
      <div className={drawer ? "drawercontent" : "modalcontent"}>
        {children}
      </div>
      {footer && <div className="drawerfoot">{footer}</div>}
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
