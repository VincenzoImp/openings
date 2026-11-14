import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { Icon } from "../../ui/Icon";
import { STEPS } from "./model";

/** Dots joined by a line; done steps carry a check, the current one a ring. */
export function Stepper({ current }: { current: number }) {
  return (
    <nav className="setup-steps" aria-label="Setup steps">
      <ol>
        {STEPS.map((step, index) => (
          <li
            key={step.id}
            className={cx(
              index < current && "is-done",
              index === current && "is-current",
            )}
            aria-current={index === current ? "step" : undefined}
          >
            <span className="setup-dot" aria-hidden="true">
              {index < current && <Icon icon={Check} size="sm" />}
            </span>
            <span className="setup-step-label">{step.label}</span>
          </li>
        ))}
      </ol>
    </nav>
  );
}

/**
 * One step: its title, a one-line lead, the content and the footer with
 * Back, Skip and the one filled button. On a phone the footer sticks above
 * the bottom bar.
 */
export function StepFrame({
  title,
  lead,
  children,
  primary,
  onBack,
  onSkip,
  busy = false,
}: {
  title: string;
  lead?: ReactNode;
  children: ReactNode;
  primary: { label: string; onClick?: () => void; form?: string };
  onBack?: () => void;
  onSkip?: () => void;
  busy?: boolean;
}) {
  return (
    <section className="setup-card" aria-labelledby="setup-title">
      <header className="setup-head">
        <h1 id="setup-title">{title}</h1>
        {lead && <p className="setup-lead">{lead}</p>}
      </header>
      <div className="setup-body">{children}</div>
      <footer className="setup-foot">
        {onBack && (
          <Button variant="ghost" onClick={onBack}>
            Back
          </Button>
        )}
        <span className="setup-foot-spacer" />
        {onSkip && (
          <Button variant="ghost" onClick={onSkip}>
            Skip
          </Button>
        )}
        <Button
          variant="primary"
          type={primary.form ? "submit" : "button"}
          form={primary.form}
          disabled={busy}
          onClick={primary.onClick}
        >
          {primary.label}
        </Button>
      </footer>
    </section>
  );
}
