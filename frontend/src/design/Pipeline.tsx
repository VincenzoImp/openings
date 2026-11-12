import type { ReactNode } from "react";
import { cx } from "./classes";

export interface PipelineStep {
  label: string;
  /** Undefined while the number is loading. */
  value?: number;
  href: string;
  /** The step the owner acts on is shown in the ready colour. */
  ready?: boolean;
}

/** The stages of the pipeline as one strip of counts; each opens its list. */
export function Pipeline({
  label,
  steps,
}: {
  label: string;
  steps: PipelineStep[];
}) {
  return (
    <nav className="pipeline num" aria-label={label}>
      {steps.map((step) => (
        <a
          key={step.label}
          href={step.href}
          className={cx(step.ready && "is-ready")}
        >
          <strong>{step.value ?? "–"}</strong>
          <span className="caption">{step.label}</span>
        </a>
      ))}
    </nav>
  );
}

/** A row of numbers with their names. */
export function Stats({ children }: { children: ReactNode }) {
  return <dl className="stats num">{children}</dl>;
}
export function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: ReactNode;
  note?: string;
}) {
  return (
    <div className="stat">
      <dt className="caption">{label}</dt>
      <dd>
        <strong>{value}</strong>
        {note && <span className="caption">{note}</span>}
      </dd>
    </div>
  );
}
