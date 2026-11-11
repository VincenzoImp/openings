import type { ReactNode } from "react";
import { cx } from "./classes";
import { Icon, type IconName } from "./Icon";

type BannerTone = "neutral" | "info" | "attention" | "danger";
const bannerIcons: Record<BannerTone, IconName> = {
  neutral: "info",
  info: "info",
  attention: "warning",
  danger: "error",
};

/** Advice or a problem, stated before the action it concerns. */
export function Banner({
  tone = "neutral",
  title,
  children,
  action,
  role,
  className,
}: {
  tone?: BannerTone;
  title?: string;
  children?: ReactNode;
  /** A button or link at the end of the banner. */
  action?: ReactNode;
  /** "alert" for an error that just happened, "status" for progress. */
  role?: "alert" | "status";
  className?: string;
}) {
  return (
    <div
      className={cx("banner", tone !== "neutral" && tone, className)}
      role={role}
    >
      <Icon name={bannerIcons[tone]} />
      <div className="grow">
        {title && <div className="title">{title}</div>}
        {children}
      </div>
      {action}
    </div>
  );
}

/** What a list or screen shows when it has nothing, with the next step. */
export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <h2 className="title">{title}</h2>
      {children && <p>{children}</p>}
      {action && <div className="row">{action}</div>}
    </div>
  );
}

export function Loading({ label = "Loading workspace…" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

/** A problem with a way out: the message and an optional retry. */
export function ErrorBanner({
  message,
  retry,
  retryLabel = "Try again",
}: {
  message: string;
  retry?: () => void;
  retryLabel?: string;
}) {
  return (
    <Banner tone="danger" role="alert">
      {message}{" "}
      {retry && (
        <button type="button" className="link" onClick={retry}>
          {retryLabel}
        </button>
      )}
    </Banner>
  );
}

/**
 * The actions that end a task. With `sticky` it stays above the bottom bar on
 * narrow screens, so the main action is always in reach.
 */
export function ActionBar({
  sticky = false,
  label,
  children,
}: {
  sticky?: boolean;
  label?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cx("actionbar", sticky && "sticky-actions")}
      role="group"
      aria-label={label}
    >
      {children}
    </div>
  );
}
