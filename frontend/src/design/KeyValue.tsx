import { useState } from "react";
import { Button, IconButton } from "./Button";
import { Switch } from "./Field";
import {
  asFields,
  describe,
  editableAsFields,
  fromRows,
  kvTypes,
  newRow,
  problem,
  retype,
  toRows,
  type KvRow,
  type KvType,
} from "./kv";

/** A structured value shown as nested lists, never as JSON text. */
export function ValueTree({ value }: { value: unknown }) {
  if (Array.isArray(value))
    return value.length ? (
      <ol className="tree">
        {value.map((item, index) => (
          <li key={index}>
            <ValueTree value={item} />
          </li>
        ))}
      </ol>
    ) : (
      <span className="muted">Empty list</span>
    );
  if (value && typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length ? (
      <dl className="tree">
        {entries.map(([key, item]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>
              <ValueTree value={item} />
            </dd>
          </div>
        ))}
      </dl>
    ) : (
      <span className="muted">Empty</span>
    );
  }
  if (value === null || value === undefined || value === "")
    return <span className="muted">Empty</span>;
  return (
    <>{typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}</>
  );
}

/**
 * Free-form values as rows of key, type and value. A nested value is shown
 * read-only and collapsed; an object can be opened for editing one level down.
 * `onChange` receives the object and what stops it from being saved, if anything.
 */
export function KeyValueEditor({
  label,
  value,
  onChange,
  addLabel = "Add a detail",
  reserved,
  nested = false,
}: {
  /** What the rows are, for assistive technology: "Other details". */
  label: string;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>, problem: string | null) => void;
  addLabel?: string;
  /** Keys that have a dedicated field elsewhere. */
  reserved?: string[];
  nested?: boolean;
}) {
  const [rows, setRows] = useState(() => toRows(value));
  const error = problem(rows, reserved);
  const update = (next: KvRow[]) => {
    setRows(next);
    onChange(fromRows(next), problem(next, reserved));
  };
  const replace = (row: KvRow) =>
    update(rows.map((item) => (item.id === row.id ? row : item)));
  return (
    <div className="kv" role="group" aria-label={label}>
      {!!rows.length && (
        <div className="kv-row kv-head" aria-hidden="true">
          <span>Key</span>
          <span>Type</span>
          <span>Value</span>
          <span />
        </div>
      )}
      {rows.map((row) => {
        const name = row.key.trim() || "this row";
        return (
          <div className="kv-row" key={row.id}>
            <input
              className="input mono"
              aria-label="Key"
              value={row.key}
              maxLength={100}
              onChange={(event) => replace({ ...row, key: event.target.value })}
            />
            <select
              className="input"
              aria-label={`Type of ${name}`}
              value={row.type}
              onChange={(event) =>
                replace(
                  retype(
                    row,
                    event.target.value as Exclude<KvType, "structured">,
                  ),
                )
              }
            >
              {row.type === "structured" && (
                <option value="structured">Structured</option>
              )}
              {Object.entries(kvTypes).map(([type, text]) => (
                <option key={type} value={type}>
                  {text}
                </option>
              ))}
            </select>
            <div className="kv-value">
              {row.type === "boolean" ? (
                <Switch
                  label={`Value of ${name}`}
                  checked={Boolean(row.value)}
                  onChange={(checked) => replace({ ...row, value: checked })}
                >
                  {row.value ? "Yes" : "No"}
                </Switch>
              ) : row.type === "structured" ? (
                row.fields ? (
                  <KeyValueEditor
                    nested
                    label={`Fields of ${name}`}
                    addLabel="Add a field"
                    value={row.value as Record<string, unknown>}
                    // The nested editor owns its rows; this row mirrors them.
                    onChange={(object, error) =>
                      replace({ ...row, fields: toRows(object), error })
                    }
                  />
                ) : (
                  <details className="kv-tree">
                    <summary>{describe(row.value)}</summary>
                    <ValueTree value={row.value} />
                  </details>
                )
              ) : row.type === "text" && /\n/.test(String(row.value ?? "")) ? (
                <textarea
                  className="input"
                  aria-label={`Value of ${name}`}
                  rows={3}
                  value={String(row.value ?? "")}
                  onChange={(event) =>
                    replace({ ...row, value: event.target.value })
                  }
                />
              ) : (
                <input
                  className="input"
                  aria-label={
                    row.type === "list"
                      ? `Value of ${name}, separated by commas`
                      : `Value of ${name}`
                  }
                  type={row.type === "number" ? "number" : "text"}
                  step="any"
                  value={String(row.value ?? "")}
                  onChange={(event) =>
                    replace({ ...row, value: event.target.value })
                  }
                />
              )}
              {!nested && editableAsFields(row) && (
                <Button
                  type="button"
                  size="sm"
                  variant="quiet"
                  data-dirty-control="true"
                  onClick={() => replace(asFields(row))}
                >
                  Edit as fields
                </Button>
              )}
            </div>
            <IconButton
              icon="close"
              label={`Remove ${name}`}
              data-dirty-control="true"
              onClick={() => update(rows.filter((item) => item.id !== row.id))}
            />
          </div>
        );
      })}
      {error && rows.length > 0 && (
        <p className="kv-error" role="status">
          {error}
        </p>
      )}
      <div>
        <Button
          type="button"
          size="sm"
          icon="plus"
          data-dirty-control="true"
          onClick={() => update([...rows, newRow()])}
        >
          {addLabel}
        </Button>
      </div>
    </div>
  );
}
