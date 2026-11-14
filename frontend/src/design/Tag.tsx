import type { ReactNode } from "react";
import { actorPhrase } from "./actor";
import { cx, tagClass, type Tone } from "./classes";

/** A short state or signal. The text carries the meaning; the tone supports it. */
export function Tag({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
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

/** Who did it, in plain words: "by you", "by <token name>", "by job sources". */
export function ActorPhrase({
  actor,
  className,
}: {
  actor?: string | null;
  className?: string;
}) {
  const text = actorPhrase(actor);
  return text ? <span className={cx("caption", className)}>{text}</span> : null;
}
