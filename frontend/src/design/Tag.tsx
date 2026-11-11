import type { ReactNode } from "react";
import { actorChip, type ActorLike } from "./actor";
import { cx, tagClass, type Tone } from "./classes";

/** A short state or signal. The text carries the meaning; the tone supports it. */
export function Tag({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone | "green" | "amber";
  className?: string;
  children: ReactNode;
}) {
  return <span className={tagClass(tone, className)}>{children}</span>;
}

/** A number beside a label; `label` says what is counted for screen readers. */
export function Count({
  value,
  label,
  quiet = false,
  className,
}: {
  value: number;
  label?: string;
  quiet?: boolean;
  className?: string;
}) {
  return (
    <>
      <span
        className={cx("count num", quiet && "quiet", className)}
        aria-hidden={label ? true : undefined}
      >
        {value}
      </span>
      {label && <span className="sr">, {label}</span>}
    </>
  );
}

/** Who did it: the owner, an agent with its token name, the system or unknown. */
export function ActorChip({
  actor,
  detail,
  className,
}: {
  actor?: ActorLike | null;
  /** What the actor was doing, for example the workflow of a run. */
  detail?: string;
  className?: string;
}) {
  const chip = actorChip(actor);
  return (
    <span
      className={cx(
        "actor",
        chip.tone === "system" ? "" : chip.tone,
        className,
      )}
    >
      {chip.text}
      {detail ? ` · ${detail}` : ""}
    </span>
  );
}
