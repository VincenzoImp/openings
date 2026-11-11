import type { ReactNode } from "react";
import type { PolicyItem, PolicySection, PolicySignal } from "../../api";
import { policySections } from "../../api";
import { Banner, Button, Field, ValueTree } from "../../design";
import {
  actionWords,
  scopeLabels,
  sectionWords,
  valueTypeLabels,
  type ItemDraft,
} from "./model";

/**
 * The form that adds or edits one item. The draft lives in the section, so the
 * text survives when the section is read again after a conflict.
 */
export function ItemForm({
  section,
  item,
  draft,
  onDraft,
  signals,
  conflict,
  busy,
  onSave,
  onCancel,
  extra,
}: {
  section: PolicySection;
  /** The item being edited; none for a new one. */
  item?: PolicyItem;
  draft: ItemDraft;
  onDraft: (draft: ItemDraft) => void;
  signals: PolicySignal[];
  /** What changed elsewhere while this form was open. */
  conflict?: string;
  busy: boolean;
  onSave: () => void;
  onCancel: () => void;
  /** Controls beside Cancel, such as moving the item. */
  extra?: ReactNode;
}) {
  const words = sectionWords[section.section];
  const set = (patch: Partial<ItemDraft>) => onDraft({ ...draft, ...patch });
  const signal = signals.find((entry) => entry.signal === draft.signal);
  const operator =
    signal?.operators.find((entry) => entry.operator === draft.operator) ||
    signal?.operators[0];
  const structured = item?.value_type === "structured";
  return (
    <form
      className="grow edit-grid"
      aria-label={
        item ? `Edit the ${words.item} ${item.label}` : `New ${words.item}`
      }
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
    >
      {conflict && (
        <Banner tone="attention" role="alert" className="wide">
          {conflict}
        </Banner>
      )}
      <Field
        label="Label"
        className={section.section === "writing" ? "" : "wide"}
      >
        <input
          name="label"
          required
          maxLength={200}
          autoFocus
          value={draft.label}
          onChange={(event) => set({ label: event.target.value })}
        />
      </Field>
      {section.section === "writing" && (
        <Field label="Applies to">
          <select
            name="scope"
            value={draft.scope}
            onChange={(event) =>
              set({ scope: event.target.value as ItemDraft["scope"] })
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
      <Field label="Statement" className="wide">
        <textarea
          name="statement"
          rows={3}
          maxLength={10000}
          value={draft.statement}
          onChange={(event) => set({ statement: event.target.value })}
        />
      </Field>
      {structured && draft.valueType === "keep" && (
        <div className="field wide">
          <span className="field-label">Copied value</span>
          <details className="kv-tree" open>
            <summary>
              Kept as it was copied. Choose a kind of value to replace it.
            </summary>
            <ValueTree value={item.value} />
          </details>
        </div>
      )}
      <Field
        label="Value"
        hint={
          draft.valueType === "list"
            ? "Separate the entries with commas."
            : "Optional, when the item has a number, a date or a list."
        }
      >
        {draft.valueType === "none" || draft.valueType === "keep" ? (
          <input name="value" disabled value="" readOnly />
        ) : draft.valueType === "boolean" ? (
          <select
            name="value"
            value={draft.value === "true" ? "true" : "false"}
            onChange={(event) => set({ value: event.target.value })}
          >
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        ) : (
          <input
            name="value"
            type={
              draft.valueType === "number"
                ? "number"
                : draft.valueType === "date"
                  ? "date"
                  : "text"
            }
            step="any"
            required
            value={draft.value}
            onChange={(event) => set({ value: event.target.value })}
          />
        )}
      </Field>
      <Field label="Kind of value">
        <select
          name="value_type"
          value={draft.valueType}
          onChange={(event) =>
            set({
              valueType: event.target.value as ItemDraft["valueType"],
              value: event.target.value === "boolean" ? "true" : "",
            })
          }
        >
          {structured && <option value="keep">Keep as copied</option>}
          <option value="none">No value</option>
          {Object.entries(valueTypeLabels).map(([type, label]) => (
            <option key={type} value={type}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label="Note"
        hint="Optional, for yourself and the agent."
        className="wide"
      >
        <input
          name="note"
          maxLength={4000}
          value={draft.note}
          onChange={(event) => set({ note: event.target.value })}
        />
      </Field>
      {section.section === "decision" && (
        <>
          <Field
            label="Collection signal"
            hint="Optional. A rule on a signal can later be applied as soon as a job is collected."
            className={signal ? "" : "wide"}
          >
            <select
              name="signal"
              value={draft.signal}
              onChange={(event) =>
                set({ signal: event.target.value, operator: "", ruleValue: "" })
              }
            >
              <option value="">No signal: the agent applies this rule</option>
              {signals.map((entry) => (
                <option key={entry.signal} value={entry.signal}>
                  {entry.label}
                </option>
              ))}
            </select>
          </Field>
          {signal && operator && (
            <>
              <Field label="Then">
                <select
                  name="action"
                  value={draft.action}
                  onChange={(event) => set({ action: event.target.value })}
                >
                  {Object.entries(actionWords).map(([action, label]) => (
                    <option key={action} value={action}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              {operator.value_type !== "boolean" && (
                <Field
                  label={
                    operator.value_type === "number"
                      ? "At least this confidence"
                      : "Compared with"
                  }
                  hint={
                    operator.value_type === "number"
                      ? "From 0 to 1."
                      : `${signal.description} Separate the entries with commas.`
                  }
                >
                  <input
                    name="rule_value"
                    required
                    type={operator.value_type === "number" ? "number" : "text"}
                    min={0}
                    max={1}
                    step="any"
                    value={draft.ruleValue}
                    onChange={(event) => set({ ruleValue: event.target.value })}
                  />
                </Field>
              )}
              {signal.operators.length > 1 && (
                <Field label="Applies when the signal">
                  <select
                    name="operator"
                    value={operator.operator}
                    onChange={(event) => set({ operator: event.target.value })}
                  >
                    <option value="not_in">has a value outside the list</option>
                    <option value="in">has a value in the list</option>
                  </select>
                </Field>
              )}
            </>
          )}
        </>
      )}
      <div className="row wide">
        <Button variant="primary" size="sm" loading={busy}>
          {item ? `Save ${words.item}` : words.add}
        </Button>
        <Button type="button" variant="quiet" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        {extra}
        <span className="caption grow">
          Saving makes this version {section.version + 1} of{" "}
          {policySections[section.section]}
          {item?.confirmed === false ? " and confirms it" : ""}.
        </span>
      </div>
    </form>
  );
}
