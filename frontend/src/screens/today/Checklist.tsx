import { useId } from "react";
import { Check } from "lucide-react";
import type { useSetup } from "../../query/setup";
import type { SetupStep } from "../setup/checklist";
import { href, navigate } from "../../shell/router";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";

const HINTS: Record<SetupStep, string> = {
  about: "Your name, the roles you want and where.",
  jobs: "A search that runs on its own, or one job by its link.",
  cv: "Paste your CV, or start from the example template.",
};

/**
 * The setup checklist, read from server facts: each thing a workspace needs
 * with the button that does it, and how many are done. On an empty workspace
 * it is all of Today and its next step is the one filled button; beside
 * applications (`compact`) every button is secondary.
 */
export function Checklist({
  setup,
  compact = false,
}: {
  setup: ReturnType<typeof useSetup>;
  compact?: boolean;
}) {
  const id = useId();
  const next = setup.items.find((item) => !item.done);
  return (
    <section
      className="today-setup"
      data-compact={compact || undefined}
      aria-labelledby={id}
    >
      <header className="today-section-head">
        <h2 id={id}>Set up your workspace</h2>
        <span className="today-setup-progress">
          {setup.done} of {setup.total} done
        </span>
      </header>
      <ol className="today-checklist">
        {setup.items.map((item, index) => (
          <li key={item.step} data-done={item.done || undefined}>
            <span className="today-check" aria-hidden="true">
              {item.done ? <Icon icon={Check} size="sm" /> : index + 1}
            </span>
            <span className="today-check-text">
              <span className="today-check-title">
                {item.title}
                {item.done && <span className="ui-sr"> (done)</span>}
              </span>
              {!compact && !item.done && (
                <span className="today-check-hint">{HINTS[item.step]}</span>
              )}
            </span>
            {item.done ? (
              <span className="today-check-done">Done</span>
            ) : (
              <Button
                size={compact ? "sm" : "md"}
                variant={!compact && item === next ? "primary" : "secondary"}
                onClick={() => navigate(href("setup", {}, { step: item.step }))}
              >
                {item.action}
              </Button>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
