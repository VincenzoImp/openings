import { useState, type ReactNode } from "react";
import type {
  PreferenceItem,
  PreferenceSection,
  WritingScope,
} from "../../api";
import {
  Banner,
  Button,
  Field,
  IconButton,
  Statement,
  StatementList,
  Tag,
} from "../../design";
import { ConfirmDialog } from "../../library/common";
import { useWorkspace } from "../../state";
import { emptyWords, itemName, moved, saved, scopeLabels } from "./model";

export type Outcome = "ok" | "conflict" | "error";
/**
 * Replace a section's statements with `items`; the screen applies the answer,
 * or reads Preferences again after a conflict.
 */
export type Save = (
  section: PreferenceSection,
  items: PreferenceItem[],
  message: string,
  /** True when a form keeps the unsaved text and reports a conflict itself. */
  form?: boolean,
) => Promise<Outcome>;

interface Editing {
  /** The statement's place when the form opened; null for a new one. */
  index: number | null;
  /** Its text then, to find it again after the section is read again. */
  original: string | null;
  text: string;
  scope: WritingScope;
  conflict?: boolean;
}
const CHANGED =
  "This section changed in another session. Your text is kept: check the list, then save again.";

/** The form that writes one statement, inline in the list. */
function ItemForm({
  name,
  writing,
  editing,
  busy,
  onChange,
  onSave,
  onCancel,
}: {
  name: string;
  writing: boolean;
  editing: Editing;
  busy: boolean;
  onChange: (patch: Partial<Editing>) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <form
      className="grow edit-grid"
      aria-label={
        editing.original === null
          ? `New statement in ${name}`
          : `Edit the statement ${itemName(editing.original)}`
      }
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
    >
      {editing.conflict && (
        <Banner tone="attention" role="alert" className="wide">
          {CHANGED}
        </Banner>
      )}
      <Field label="Statement" className="wide">
        <textarea
          name="text"
          rows={3}
          maxLength={2000}
          required
          autoFocus
          value={editing.text}
          onChange={(event) => onChange({ text: event.target.value })}
        />
      </Field>
      {writing && (
        <Field label="Applies to">
          <select
            name="scope"
            value={editing.scope}
            onChange={(event) =>
              onChange({ scope: event.target.value as WritingScope })
            }
          >
            {Object.entries(scopeLabels).map(([scope, label]) => (
              <option key={scope} value={scope}>
                {label}
              </option>
            ))}
          </select>
        </Field>
      )}
      <div className="row wide">
        <Button variant="primary" size="sm" loading={busy}>
          Save
        </Button>
        <Button type="button" variant="quiet" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** The `…` of a statement: it shows the less frequent actions. */
function ItemMenu({
  name,
  disabled,
  onDelete,
}: {
  name: string;
  disabled: boolean;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      {open && (
        <Button
          size="sm"
          variant="quiet danger"
          aria-label={`Delete ${name}`}
          disabled={disabled}
          onClick={() => {
            setOpen(false);
            onDelete();
          }}
        >
          Delete
        </Button>
      )}
      <IconButton
        icon="more"
        label={`More actions for ${name}`}
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen(!open)}
      />
    </>
  );
}

/** One section of Preferences: its statements, in order, each edited in place. */
export function SectionCard({
  section,
  busy,
  save,
  children,
}: {
  section: PreferenceSection;
  busy: boolean;
  save: Save;
  /** What the section shows under its statements (the settings of Facts). */
  children?: ReactNode;
}) {
  const name = section.section;
  const writing = name === "writing";
  const { notify } = useWorkspace();
  const [editing, setEditing] = useState<Editing | null>(null);
  const [removing, setRemoving] = useState<number | null>(null);
  const items = section.items;
  const open = (index: number | null) => {
    const item = index === null ? null : items[index];
    setEditing({
      index,
      original: item ? item.text : null,
      text: item ? item.text : "",
      scope: item?.scope || "all",
    });
  };
  async function submit() {
    if (!editing) return;
    const text = editing.text.trim();
    if (!text) return notify("Write the statement.", true);
    const draft = writing ? { text, scope: editing.scope } : { text };
    const next = saved(items, draft, editing.index ?? -1, editing.original);
    const outcome = await save(
      section,
      next,
      editing.original === null ? `Added to ${section.title}.` : "Saved.",
      true,
    );
    if (outcome === "ok") setEditing(null);
    else if (outcome === "conflict")
      setEditing((current) => current && { ...current, conflict: true });
  }
  const reorder = (index: number, step: -1 | 1) => {
    // The buttons stay enabled while a write runs, so focus stays on them.
    if (busy) return;
    return save(section, moved(items, index, step), "Order saved.");
  };
  const form = (
    <ItemForm
      name={section.title}
      writing={writing}
      editing={editing!}
      busy={busy}
      onChange={(patch) =>
        setEditing((current) => current && { ...current, ...patch })
      }
      onSave={submit}
      onCancel={() => setEditing(null)}
    />
  );
  const shown = editing && editing.index !== null ? editing.index : -1;
  return (
    <section className="card" aria-labelledby={`preferences-${name}`}>
      <header>
        <div className="grow">
          <h2 id={`preferences-${name}`} tabIndex={-1}>
            {section.title}
          </h2>
          <div className="caption">{section.description}</div>
        </div>
      </header>
      {items.length || editing ? (
        <StatementList label={`${section.title} statements`}>
          {items.map((item, index) => {
            const label = itemName(item.text);
            return (
              <Statement
                key={`${index}-${item.text}`}
                name={label}
                editing={shown === index}
                disabled={!!editing}
                onUp={index ? () => reorder(index, -1) : undefined}
                onDown={
                  index < items.length - 1 ? () => reorder(index, 1) : undefined
                }
                tags={writing && <Tag>{scopeLabels[item.scope || "all"]}</Tag>}
                actions={
                  <>
                    <Button
                      size="sm"
                      variant="quiet"
                      aria-label={`Edit ${label}`}
                      disabled={!!editing}
                      onClick={() => open(index)}
                    >
                      Edit
                    </Button>
                    <ItemMenu
                      name={label}
                      disabled={busy || !!editing}
                      onDelete={() => setRemoving(index)}
                    />
                  </>
                }
              >
                {shown === index ? (
                  form
                ) : (
                  <div className="prose">{item.text}</div>
                )}
              </Statement>
            );
          })}
          {editing && shown < 0 && (
            <Statement name="the new statement" editing movable={false}>
              {form}
            </Statement>
          )}
        </StatementList>
      ) : (
        <p className="body muted">{emptyWords[name]}</p>
      )}
      <footer>
        <Button
          size="sm"
          icon="plus"
          disabled={!!editing}
          aria-label={`Add to ${section.title}`}
          onClick={() => open(null)}
        >
          Add
        </Button>
      </footer>
      {children}
      {removing !== null && items[removing] && (
        <ConfirmDialog
          title="Delete this statement?"
          confirm="Delete statement"
          keep="Keep statement"
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            await save(
              section,
              items.filter((_, index) => index !== removing),
              "Deleted.",
            );
            setRemoving(null);
          }}
        >
          <p>
            <strong>{itemName(items[removing].text, 120)}</strong> is deleted
            from {section.title}. Applications that were already prepared keep
            the copy they were written under.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
