import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { cx } from "./cx";
import { Icon, type LucideIcon } from "./Icon";
import "./page.css";

export interface Crumb {
  label: string;
  href?: string;
}

/**
 * The head of a page: the h1 and at most one action. A second-level page
 * shows its breadcrumb ("Applications / Data Engineer · Orbit"); a top-level
 * page shows none and no description.
 */
export function PageHeader({
  title,
  breadcrumb,
  action,
}: {
  title: string;
  breadcrumb?: Crumb[];
  action?: ReactNode;
}) {
  return (
    <header className="ui-page-header">
      <div className="ui-page-title">
        {breadcrumb?.length ? (
          <nav aria-label="Breadcrumb" className="ui-breadcrumb">
            <ol>
              {breadcrumb.map((crumb) => (
                <li key={crumb.label}>
                  {crumb.href ? (
                    <a href={crumb.href}>{crumb.label}</a>
                  ) : (
                    <span>{crumb.label}</span>
                  )}
                  <Icon icon={ChevronRight} size="sm" />
                </li>
              ))}
            </ol>
          </nav>
        ) : null}
        <h1>{title}</h1>
      </div>
      {action && <div className="ui-page-action">{action}</div>}
    </header>
  );
}

/**
 * What an empty place teaches: an icon tile, a title, one sentence and the
 * action that fills it (primary), with an alternative (ghost). A manual path
 * always exists.
 */
export function EmptyState({
  icon,
  title,
  children,
  actions,
  className,
}: {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("ui-empty", className)}>
      <span className="ui-empty-icon">
        <Icon icon={icon} size="lg" />
      </span>
      <h2 className="ui-empty-title">{title}</h2>
      {children && <p className="ui-empty-body">{children}</p>}
      {actions && <div className="ui-empty-actions">{actions}</div>}
    </div>
  );
}

/** A static placeholder line while content loads; it does not shimmer. */
export function Skeleton({
  width = "100%",
  height = 12,
  className,
}: {
  width?: number | string;
  height?: number;
  className?: string;
}) {
  return (
    <span
      className={cx("ui-skeleton", className)}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

/** Skeleton list rows, announced once as loading. */
export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="ui-skeleton-rows" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <div className="ui-skeleton-row" key={index}>
          <Skeleton width={`${62 - (index % 3) * 12}%`} height={12} />
          <Skeleton width={`${38 - (index % 2) * 10}%`} height={10} />
        </div>
      ))}
    </div>
  );
}

/** The meta line of a record: icon and text pairs (14 px icons). */
export function MetaLine({
  items,
}: {
  items: { icon: LucideIcon; text: ReactNode; label?: string }[];
}) {
  return (
    <ul className="ui-metaline">
      {items.map((item, index) => (
        <li key={index} aria-label={item.label}>
          <Icon icon={item.icon} size="sm" />
          <span>{item.text}</span>
        </li>
      ))}
    </ul>
  );
}

/** Long reading text (a posting, a letter): 14.5/23, at most 66ch. */
export function Prose({ children }: { children: ReactNode }) {
  return <div className="ui-prose">{children}</div>;
}

/** Properties of a record: a 120 px label column and values. */
export function Properties({
  items,
}: {
  items: { label: string; value: ReactNode }[];
}) {
  const shown = items.filter(
    (item) => item.value != null && item.value !== "",
  );
  return (
    <dl className="ui-props">
      {shown.map((item) => (
        <div className="ui-prop" key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** At most one callout per detail: a duplicate, missing text. */
export function Callout({
  icon,
  title,
  children,
  actions,
  tone,
}: {
  icon: LucideIcon;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  tone?: "warning" | "danger";
}) {
  return (
    <div className="ui-callout" data-tone={tone}>
      <Icon icon={icon} />
      <div className="ui-callout-body">
        <p className="ui-callout-title">{title}</p>
        {children && <p className="ui-callout-text">{children}</p>}
        {actions && <div className="ui-callout-actions">{actions}</div>}
      </div>
    </div>
  );
}
