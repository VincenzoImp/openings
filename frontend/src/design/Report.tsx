import { useId, type ReactNode } from "react";

/** One titled part of a report or a detail panel. */
export function ReportSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section className="sub" aria-labelledby={id}>
      <h3 id={id}>{title}</h3>
      {children}
    </section>
  );
}

/** Counts with what they count: "5 · applications marked ready: …". */
export function CountList({ children }: { children: ReactNode }) {
  return <dl className="dl counts num">{children}</dl>;
}
export function CountRow({
  count,
  children,
}: {
  count: number;
  children: ReactNode;
}) {
  return (
    <>
      <dt>{count}</dt>
      <dd>{children}</dd>
    </>
  );
}

/** The heading of one day in a timeline. */
export function DayHeading({ children }: { children: ReactNode }) {
  return <h2 className="kind eyebrow">{children}</h2>;
}

/**
 * One change in a timeline: what happened and to what, its kind, who did it
 * and when. On narrow screens the tags wrap under the text.
 */
export function TimelineEntry({
  title,
  meta,
  tag,
  actor,
  time,
}: {
  title: ReactNode;
  meta?: ReactNode;
  tag?: ReactNode;
  actor?: ReactNode;
  time?: string;
}) {
  return (
    <li>
      <div className="grow">
        <div className="title">{title}</div>
        {meta && <div className="meta">{meta}</div>}
      </div>
      {tag}
      {actor}
      {time && <span className="caption num">{time}</span>}
    </li>
  );
}
