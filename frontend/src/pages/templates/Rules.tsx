import { useState, type FormEvent } from "react";
import {
  api,
  newId,
  version,
  type Json,
  type RuleStatement,
  type Template,
} from "../../api";
import {
  Button,
  Field,
  KeyValueEditor,
  Statement,
  StatementList,
  Tag,
} from "../../design";
import { useWorkspace } from "../../state";

const TYPED = ["max_pages", "max_bullets", "max_bullet_chars", "statements"];
const LIMITS: [string, string, string, number, number][] = [
  ["max_pages", "Pages", "At most.", 1, 30],
  ["max_bullets", "Bullets per entry", "At most.", 1, 100],
  ["max_bullet_chars", "Bullet length", "Characters, at most.", 20, 5000],
];
type Draft = Pick<RuleStatement, "label" | "statement" | "scope">;

/** The rules of a template: guidance, typed limits, rule statements and the rest. */
export function RulesTab({ template }: { template: Template }) {
  const { mutate, pending, notify } = useWorkspace();
  const [statements, setStatements] = useState<RuleStatement[]>(
    template.rules.statements || [],
  );
  const [editing, setEditing] = useState<{ id: string; draft: Draft } | null>(
    null,
  );
  const [rest, setRest] = useState<{ value: Json; problem: string | null }>(
    () => ({
      value: Object.fromEntries(
        Object.entries(template.rules).filter(([key]) => !TYPED.includes(key)),
      ),
      problem: null,
    }),
  );
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editing) return notify("Finish the rule you are editing first.", true);
    if (rest.problem) return notify(rest.problem, true);
    const form = new FormData(event.currentTarget);
    const limits = Object.fromEntries(
      LIMITS.map(([name]) => [name, Number(form.get(name)) || undefined]),
    );
    await mutate(
      () =>
        api(
          `/templates/${template.id}`,
          "PATCH",
          version(template, {
            guidance: form.get("guidance"),
            rules: { ...rest.value, ...limits, statements },
          }),
        ),
      "Rules saved. Applications that were already prepared keep theirs.",
    );
  }
  const move = (index: number, step: -1 | 1) =>
    setStatements((rows) => {
      const next = [...rows];
      [next[index], next[index + step]] = [next[index + step], next[index]];
      return next;
    });
  function commit() {
    if (!editing) return;
    const draft = {
      ...editing.draft,
      label: editing.draft.label.trim(),
      statement: editing.draft.statement.trim(),
      scope: editing.draft.scope?.trim() || null,
    };
    if (!draft.statement) return notify("Write the rule.", true);
    setStatements((rows) =>
      rows.some((row) => row.id === editing.id)
        ? rows.map((row) =>
            row.id === editing.id ? { ...row, ...draft } : row,
          )
        : [...rows, { id: editing.id, position: rows.length, ...draft }],
    );
    setEditing(null);
  }
  const set = (patch: Partial<Draft>) =>
    setEditing(
      (current) =>
        current && { ...current, draft: { ...current.draft, ...patch } },
    );
  const original = statements.find((row) => row.id === editing?.id);
  const editor = editing && (
    <div
      className="grow edit-grid"
      role="group"
      aria-label={original ? `Edit ${original.label || "rule"}` : "Rule"}
    >
      <Field label="Label">
        <input
          autoFocus
          maxLength={200}
          value={editing.draft.label}
          onChange={(event) => set({ label: event.target.value })}
        />
      </Field>
      <Field label="Applies to" hint="Optional: a part of the document.">
        <input
          maxLength={100}
          value={editing.draft.scope || ""}
          onChange={(event) => set({ scope: event.target.value })}
        />
      </Field>
      <Field label="Rule" className="wide">
        <textarea
          rows={3}
          maxLength={4000}
          value={editing.draft.statement}
          onChange={(event) => set({ statement: event.target.value })}
        />
      </Field>
      <div className="row wide">
        <Button
          type="button"
          size="sm"
          variant="primary"
          data-dirty-control="true"
          onClick={commit}
        >
          Done
        </Button>
        <Button
          type="button"
          size="sm"
          variant="quiet"
          onClick={() => setEditing(null)}
        >
          Discard
        </Button>
        <span className="caption grow">
          The rule is stored when you save the rules.
        </span>
      </div>
    </div>
  );
  return (
    <form onSubmit={save}>
      <div className="body stack">
        <Field
          label="Guidance for this template"
          hint="Added to the general writing instructions when this template is used."
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
      <div className="sub flush">
        <div className="spread">
          <h3>
            Rule statements{" "}
            <span className="muted num">{statements.length}</span>
          </h3>
          <Button
            type="button"
            size="sm"
            disabled={!!editing}
            onClick={() =>
              setEditing({
                id: newId().replaceAll("-", ""),
                draft: { label: "", statement: "", scope: null },
              })
            }
          >
            Add a rule
          </Button>
        </div>
        {statements.length || editing ? (
          <StatementList label="Rule statements">
            {statements.map((rule, index) => (
              <Statement
                key={rule.id}
                name={rule.label || `rule ${index + 1}`}
                editing={editing?.id === rule.id}
                disabled={!!editing}
                onUp={index ? () => move(index, -1) : undefined}
                onDown={
                  index < statements.length - 1
                    ? () => move(index, 1)
                    : undefined
                }
                label={rule.label}
                tags={rule.scope && <Tag>{rule.scope}</Tag>}
                actions={
                  <>
                    <Button
                      type="button"
                      size="sm"
                      variant="quiet"
                      disabled={!!editing}
                      aria-label={`Edit ${rule.label || `rule ${index + 1}`}`}
                      onClick={() => setEditing({ id: rule.id, draft: rule })}
                    >
                      Edit
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="quiet danger"
                      data-dirty-control="true"
                      aria-label={`Remove ${rule.label || `rule ${index + 1}`}`}
                      onClick={() =>
                        setStatements((rows) =>
                          rows.filter((row) => row.id !== rule.id),
                        )
                      }
                    >
                      Remove
                    </Button>
                  </>
                }
              >
                {editing?.id === rule.id ? (
                  editor
                ) : (
                  <div className="prose">{rule.statement}</div>
                )}
              </Statement>
            ))}
            {editing && !statements.some((row) => row.id === editing.id) && (
              <Statement name="the new rule" editing movable={false}>
                {editor}
              </Statement>
            )}
          </StatementList>
        ) : (
          <p className="claim muted">
            No rule statements yet. Say what a document from this template must
            keep: the order of sections, how a bullet starts, what is left out.
          </p>
        )}
      </div>
      <div className="sub">
        <div className="spread">
          <h3>Other settings</h3>
          <span className="caption">
            Free-form values the product does not act on
          </span>
        </div>
        <KeyValueEditor
          label="Other settings as keys and values"
          addLabel="Add a setting"
          value={rest.value}
          reserved={TYPED}
          onChange={(value, problem) => setRest({ value, problem })}
        />
      </div>
      <footer>
        <span className="muted grow">
          Applications that were already prepared keep the rules they froze.
        </span>
        <Button variant="primary" size="sm" disabled={pending}>
          Save rules
        </Button>
      </footer>
    </form>
  );
}
