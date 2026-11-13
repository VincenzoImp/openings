import { useState, type FormEvent } from "react";
import {
  api,
  newId,
  requirementKinds,
  version,
  type Application,
  type Requirement,
  type RequirementKind,
} from "../../api";
import { Button, Field, IconButton, Tag } from "../../design";
import { useWorkspace } from "../../state";

/**
 * The employer's conditions from the posting or the form: authorship,
 * attachments, references, format, language, eligibility, dates. An
 * unresolved blocking requirement keeps the application from being ready.
 */
export function Requirements({ application }: { application: Application }) {
  const { mutate, pending } = useWorkspace();
  const [items, setItems] = useState<Requirement[]>(
    application.requirements || [],
  );
  const change = (index: number, patch: Partial<Requirement>) =>
    setItems((current) =>
      current.map((item, at) => (at === index ? { ...item, ...patch } : item)),
    );
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(
      () =>
        api(
          `/applications/${application.id}`,
          "PATCH",
          version(application, {
            requirements: items.map((item) => ({
              ...item,
              text: item.text.trim(),
              note: item.note.trim(),
            })),
          }),
        ),
      "Requirements saved.",
    );
  }
  return (
    <form className="stack" onSubmit={save} aria-label="Requirements">
      <p className="muted">
        An unresolved blocking requirement keeps this application from being
        marked ready and stops your agent from writing for it.
      </p>
      {!items.length && <p className="muted">No requirement is recorded.</p>}
      <ul className="list requirements">
        {items.map((item, index) => (
          <li key={item.id} className="stack">
            <div className="spread wrap">
              <div className="row">
                <strong>{requirementKinds[item.kind] || item.kind}</strong>
                {item.resolved ? (
                  <Tag tone="ready">Resolved</Tag>
                ) : item.blocking ? (
                  <Tag tone="danger">Blocking</Tag>
                ) : (
                  <Tag tone="attention">Open</Tag>
                )}
              </div>
              <IconButton
                icon="trash"
                label={`Remove requirement ${index + 1}`}
                data-dirty-control="true"
                onClick={() =>
                  setItems((current) => current.filter((_, at) => at !== index))
                }
              />
            </div>
            <div className="form-grid">
              <Field label="Kind">
                <select
                  value={item.kind}
                  onChange={(event) =>
                    change(index, {
                      kind: event.target.value as RequirementKind,
                    })
                  }
                >
                  {Object.entries(requirementKinds).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={item.blocking}
                  onChange={(event) =>
                    change(index, { blocking: event.target.checked })
                  }
                />
                <span>Blocking</span>
              </label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={item.resolved}
                  onChange={(event) =>
                    change(index, { resolved: event.target.checked })
                  }
                />
                <span>Resolved</span>
              </label>
              <Field label="Requirement" className="wide">
                <textarea
                  rows={2}
                  required
                  maxLength={2000}
                  value={item.text}
                  onChange={(event) =>
                    change(index, { text: event.target.value })
                  }
                />
              </Field>
              <Field label="Resolution or open question" className="wide">
                <input
                  maxLength={2000}
                  value={item.note}
                  placeholder="Your decision, a supplied file or a question to ask"
                  onChange={(event) =>
                    change(index, { note: event.target.value })
                  }
                />
              </Field>
            </div>
          </li>
        ))}
      </ul>
      <div className="row">
        <Button
          type="button"
          size="sm"
          icon="plus"
          data-dirty-control="true"
          disabled={items.length >= 100}
          onClick={() =>
            setItems((current) => [
              ...current,
              {
                id: newId().replace(/-/g, "").slice(0, 12),
                kind: "other",
                text: "",
                blocking: false,
                resolved: false,
                note: "",
              },
            ])
          }
        >
          Add requirement
        </Button>
        <Button variant="primary" size="sm" disabled={pending}>
          Save requirements
        </Button>
      </div>
    </form>
  );
}
