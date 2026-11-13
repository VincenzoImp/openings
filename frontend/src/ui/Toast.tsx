import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CircleAlert, CircleCheck, X } from "lucide-react";
import { Kbd } from "./Button";
import { Icon, type LucideIcon } from "./Icon";
import { isModKey, isTyping } from "./keys";
import "./toast.css";

/** How long a toast stays, unless the pointer or focus is on it. */
export const TOAST_MS = 6000;

export interface ToastAction {
  label: string;
  run: () => void;
  /** ⌘Z for Undo; shown as a hint and bound while the toast is shown. */
  undo?: boolean;
}
export interface ToastOptions {
  /** Past tense, naming the object: Dismissed "Backend Engineer". */
  message: string;
  /** An action toast (inverted) by default; status toasts carry an icon. */
  tone?: "action" | "success" | "error";
  icon?: LucideIcon;
  action?: ToastAction;
}
interface Shown extends ToastOptions {
  key: number;
}

/**
 * One toast, drawn. An action toast uses the primary fill; a success or
 * error toast is a surface with a coloured icon.
 */
export function ToastView({
  message,
  tone = "action",
  icon,
  action,
  onClose,
  onHold,
}: ToastOptions & {
  onClose?: () => void;
  onHold?: (held: boolean) => void;
}) {
  const glyph =
    icon ??
    (tone === "success" ? CircleCheck : tone === "error" ? CircleAlert : null);
  return (
    <div
      className="ui-toast"
      data-tone={tone}
      onMouseEnter={() => onHold?.(true)}
      onMouseLeave={() => onHold?.(false)}
      onFocus={() => onHold?.(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          onHold?.(false);
      }}
    >
      {glyph && <Icon icon={glyph} className="ui-toast-icon" />}
      <span className="ui-toast-message">{message}</span>
      {action && (
        <button
          type="button"
          className="ui-toast-action"
          aria-keyshortcuts={action.undo ? "Meta+Z Control+Z" : undefined}
          onClick={() => {
            onClose?.();
            action.run();
          }}
        >
          {action.label}
          {action.undo && <Kbd>⌘Z</Kbd>}
        </button>
      )}
      {onClose && (
        <button
          type="button"
          className="ui-toast-close"
          aria-label="Close"
          onClick={onClose}
        >
          <Icon icon={X} size="sm" />
        </button>
      )}
    </div>
  );
}

const ToastContext = createContext<{
  show: (toast: ToastOptions) => void;
  close: () => void;
} | null>(null);

/** Shows a toast; a new one replaces the one on screen. */
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw Error("useToast needs a ToastProvider.");
  return context;
}

/**
 * At most one toast at a time, bottom-left of the content on wide screens and
 * full-width above the bottom bar on phones. It goes after six seconds, held
 * while hovered or focused; an error stays until closed. Announced politely,
 * errors assertively. ⌘Z runs an Undo while one is shown.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Shown | null>(null);
  const [held, setHeld] = useState(false);
  const counter = useRef(0);
  const close = useCallback(() => {
    setToast(null);
    setHeld(false);
  }, []);
  const show = useCallback((options: ToastOptions) => {
    counter.current += 1;
    setHeld(false);
    setToast({ ...options, key: counter.current });
  }, []);

  useEffect(() => {
    if (!toast || held || toast.tone === "error") return;
    const timer = setTimeout(close, TOAST_MS);
    return () => clearTimeout(timer);
  }, [toast, held, close]);

  useEffect(() => {
    const undo = toast?.action?.undo ? toast.action : null;
    if (!undo) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "z" || event.shiftKey) return;
      if (!isModKey(event) || isTyping(event.target)) return;
      event.preventDefault();
      close();
      undo.run();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toast, close]);

  const value = useMemo(() => ({ show, close }), [show, close]);
  const error = toast?.tone === "error";
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="ui-toast-region">
        <div role="status" aria-live="polite">
          {toast && !error && (
            <ToastView
              key={toast.key}
              {...toast}
              onClose={close}
              onHold={setHeld}
            />
          )}
        </div>
        <div role="alert" aria-live="assertive">
          {toast && error && (
            <ToastView key={toast.key} {...toast} onClose={close} />
          )}
        </div>
      </div>
    </ToastContext.Provider>
  );
}
