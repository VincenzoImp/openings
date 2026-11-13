import type { FormEvent } from "react";
import { api, version, type Template } from "../../api";
import { Button, Field } from "../../design";
import { useWorkspace } from "../../state";

const LIMITS: [string, string, string, number, number][] = [
  ["max_pages", "Pages", "At most.", 1, 30],
  ["max_bullets", "Bullets per entry", "At most.", 1, 100],
  ["max_bullet_chars", "Bullet length", "Characters, at most.", 20, 5000],
];

/**
 * A template's guidance and limits. Its other keys (engine, date_format) are
 * not shown and are kept as they are; writing rules live in Preferences.
 */
export function RulesTab({ template }: { template: Template }) {
  const { mutate, pending } = useWorkspace();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const limits = Object.fromEntries(
      LIMITS.map(([name]) => [name, Number(form.get(name)) || undefined]),
    );
    // Statements moved to Preferences in 0.24; the server refuses them.
    const kept = Object.fromEntries(
      Object.entries(template.rules).filter(([key]) => key !== "statements"),
    );
    await mutate(
      () =>
        api(
          `/templates/${template.id}`,
          "PATCH",
          version(template, {
            guidance: form.get("guidance"),
            rules: { ...kept, ...limits },
          }),
        ),
      "Saved. Applications that were already prepared keep theirs.",
    );
  }
  return (
    <form onSubmit={save}>
      <div className="body stack">
        <Field
          label="Guidance for this template"
          hint="Read by your agent with your writing rules when this template is used."
        >
          <textarea name="guidance" rows={4} defaultValue={template.guidance} />
        </Field>
        <h3>Limits</h3>
        <div className="limits">
          {LIMITS.map(([name, label, hint, min, max]) => (
            <Field key={name} label={label} hint={hint}>
              <input
                name={name}
                type="number"
                min={min}
                max={max}
                defaultValue={template.rules[name] as number | undefined}
              />
            </Field>
          ))}
        </div>
        <p className="caption">
          The workspace checks bullet count and bullet length on every document
          saved with structured content. Empty means no limit.
        </p>
      </div>
      <footer>
        <span className="muted grow">
          Applications that were already prepared keep the guidance and limits
          they froze.
        </span>
        <Button variant="primary" size="sm" disabled={pending}>
          Save
        </Button>
      </footer>
    </form>
  );
}
