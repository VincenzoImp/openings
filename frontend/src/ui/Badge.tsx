import type { ReactNode } from "react";
import { cx } from "./cx";
import { formatNumber } from "./format";
import { Icon, StatusGlyph, STAGES, type LucideIcon, type Stage } from "./Icon";
import "./badge.css";

/** An informational count: a plain text-3 number. */
export function Count({ value, label }: { value: number; label?: string }) {
  return (
    <span className="ui-count" aria-label={label}>
      {formatNumber(value, { compact: true })}
    </span>
  );
}

/**
 * A "needs you" count: the accent pill, used only in the navigation and the
 * mobile bar. Nothing is shown at zero.
 */
export function NeedsCount({ value, label }: { value: number; label: string }) {
  if (!value) return null;
  return (
    <span className="ui-needs" aria-label={`${value} ${label}`}>
      {value > 99 ? "99+" : value}
    </span>
  );
}

/** A neutral fact (a skill, a language): at most three per row, then "+N". */
export function Tag({
  icon,
  children,
}: {
  icon?: LucideIcon;
  children: ReactNode;
}) {
  return (
    <span className="ui-tag">
      {icon && <Icon icon={icon} size="sm" />}
      {children}
    </span>
  );
}

/** Tags with an overflow counter after `max`. */
export function Tags({ items, max = 3 }: { items: string[]; max?: number }) {
  const shown = items.slice(0, max),
    rest = items.length - shown.length;
  return (
    <span className="ui-tags">
      {shown.map((item) => (
        <Tag key={item}>{item}</Tag>
      ))}
      {rest > 0 && (
        <span className="ui-tag" title={items.slice(max).join(", ")}>
          +{rest}
        </span>
      )}
    </span>
  );
}

/** A stage as glyph plus text, never a coloured pill. */
export function Status({
  stage,
  children,
}: {
  stage: Stage;
  children?: ReactNode;
}) {
  return (
    <span className="ui-status">
      <StatusGlyph stage={stage} />
      {children ?? STAGES[stage]}
    </span>
  );
}

export type Tone = "warning" | "danger" | "success" | "accent";

/** Text coloured by meaning, such as a deadline: the one signal of a row. */
export function ToneText({
  tone,
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <span className={cx("ui-tone", tone && `ui-tone-${tone}`)}>{children}</span>
  );
}

/** The unread dot of a list row. */
export function Dot({
  label = "Unread",
  hidden = false,
}: {
  label?: string;
  hidden?: boolean;
}) {
  return hidden ? (
    <span className="ui-dot" data-off="" aria-hidden="true" />
  ) : (
    <span className="ui-dot" role="img" aria-label={label} />
  );
}

/** Initials in a circle, for the account. */
export function Avatar({ name, size = 24 }: { name: string; size?: number }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
  return (
    <span
      className="ui-avatar"
      style={{ width: size, height: size, fontSize: Math.round(size * 0.42) }}
      aria-hidden="true"
    >
      {initials}
    </span>
  );
}
