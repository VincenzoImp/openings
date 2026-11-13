import type { ReactNode } from "react";
import { confirmLeave } from "../state";
import { Icon } from "./Icon";
import { nextTabIndex } from "./keys";

export interface Step {
  id: string;
  label: string;
  /** The state under the name: "Done · career-agent", "In progress · 3 of 6". */
  line: string;
  done: boolean;
}
const tabId = (base: string, id: string) => `${base}-step-${id}`;
const panelId = (base: string) => `${base}-panel`;

/**
 * Numbered steps as a tab list: each step shows whether it is done, and any
 * step can be opened. Arrows (up and down too, since the steps stack on a
 * phone), Home and End move and select.
 */
export function Stepper({
  steps,
  value,
  onChange,
  label,
  id,
  children,
}: {
  steps: Step[];
  value: string;
  onChange: (id: string) => void;
  label: string;
  id: string;
  /** The selected step's content, rendered as its panel. */
  children: ReactNode;
}) {
  const current = steps.findIndex((step) => step.id === value);
  return (
    <>
      <div
        className="stepper"
        role="tablist"
        aria-label={label}
        onKeyDown={(event) => {
          const key =
            event.key === "ArrowDown"
              ? "ArrowRight"
              : event.key === "ArrowUp"
                ? "ArrowLeft"
                : event.key;
          const next = nextTabIndex(key, current, steps.length);
          if (next === null) return;
          event.preventDefault();
          if (!confirmLeave()) return;
          onChange(steps[next].id);
          event.currentTarget
            .querySelectorAll<HTMLButtonElement>("[role=tab]")
            [next]?.focus();
        }}
      >
        {steps.map((step, index) => (
          <button
            type="button"
            role="tab"
            key={step.id}
            id={tabId(id, step.id)}
            aria-selected={step.id === value}
            aria-controls={panelId(id)}
            tabIndex={step.id === value ? 0 : -1}
            className={step.done ? "done" : undefined}
            onClick={() => {
              if (step.id === value || confirmLeave()) onChange(step.id);
            }}
          >
            <span className="step-mark" aria-hidden="true">
              {step.done ? <Icon name="check" /> : index + 1}
            </span>
            <span className="step-text">
              <strong>{step.label}</strong>
              <span>{step.line}</span>
            </span>
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={panelId(id)}
        aria-labelledby={tabId(id, value)}
        tabIndex={0}
      >
        {children}
      </div>
    </>
  );
}
