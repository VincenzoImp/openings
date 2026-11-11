// The rows of a key/value editor and their conversion to and from a JSON
// object, kept free of React for unit tests. A value the editor has no control
// for (an object, a mixed list, null) is "structured": it is kept as it is and
// shown read-only, or edited one level down as fields.

export type KvType = "text" | "number" | "boolean" | "list" | "structured";
export interface KvRow {
  id: number;
  key: string;
  type: KvType;
  /** The control's text for text, number and list; a boolean; or the kept value. */
  value: unknown;
  /** The top-level keys of a structured object, once "edit as fields" is chosen. */
  fields?: KvRow[];
  /** What is wrong inside `fields`, reported by their own editor. */
  error?: string | null;
}
export const kvTypes: Record<Exclude<KvType, "structured">, string> = {
  text: "Text",
  number: "Number",
  boolean: "Yes or no",
  list: "List",
};

let nextId = 1;

/** The type whose control can edit a value without changing it. */
export function typeOf(value: unknown): KvType {
  if (typeof value === "string") return "text";
  if (typeof value === "number" && Number.isFinite(value)) return "number";
  if (typeof value === "boolean") return "boolean";
  if (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every(
      (item) =>
        typeof item === "string" && item.trim() === item && !/[,\n]/.test(item),
    ) &&
    value.every(Boolean)
  )
    return "list";
  return "structured";
}

function rowOf(key: string, value: unknown): KvRow {
  const type = typeOf(value);
  return {
    id: nextId++,
    key,
    type,
    value:
      type === "number"
        ? String(value)
        : type === "list"
          ? (value as string[]).join(", ")
          : value,
  };
}

export function toRows(object: Record<string, unknown> | null | undefined) {
  return Object.entries(object || {}).map(([key, value]) => rowOf(key, value));
}

export function newRow(): KvRow {
  return { id: nextId++, key: "", type: "text", value: "" };
}

const listItems = (text: unknown) =>
  String(text ?? "")
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);

/** The JSON value of one row. */
export function valueOf(row: KvRow): unknown {
  if (row.type === "text") return String(row.value ?? "");
  if (row.type === "number") return Number(row.value);
  if (row.type === "boolean") return Boolean(row.value);
  if (row.type === "list") return listItems(row.value);
  return row.fields ? fromRows(row.fields) : row.value;
}

export function fromRows(rows: KvRow[]): Record<string, unknown> {
  return Object.fromEntries(rows.map((row) => [row.key.trim(), valueOf(row)]));
}

/** Change the type of a row, carrying the value over where it has a meaning. */
export function retype(row: KvRow, type: Exclude<KvType, "structured">): KvRow {
  const current = row.type === "structured" ? "" : valueOf(row);
  const text = Array.isArray(current) ? current.join(", ") : String(current);
  const value =
    type === "boolean"
      ? current === true || text === "true"
      : type === "number"
        ? Number.isFinite(Number(text)) && text.trim() !== ""
          ? text
          : ""
        : row.type === "boolean"
          ? ""
          : text;
  return { id: row.id, key: row.key, type, value };
}

/** Start editing the top-level keys of a structured object. */
export function asFields(row: KvRow): KvRow {
  return editableAsFields(row)
    ? { ...row, fields: toRows(row.value as Record<string, unknown>) }
    : row;
}
export function editableAsFields(row: KvRow) {
  return (
    row.type === "structured" &&
    !row.fields &&
    typeof row.value === "object" &&
    row.value !== null &&
    !Array.isArray(row.value)
  );
}

/** What stops these rows from being saved, or null. `reserved` keys are refused. */
export function problem(rows: KvRow[], reserved: string[] = []): string | null {
  const seen = new Set<string>();
  for (const row of rows) {
    const key = row.key.trim();
    if (!key) return "Give every row a key.";
    if (seen.has(key)) return `The key "${key}" is used twice.`;
    if (reserved.includes(key)) return `"${key}" has its own field above.`;
    seen.add(key);
    if (
      row.type === "number" &&
      (String(row.value).trim() === "" || !Number.isFinite(Number(row.value)))
    )
      return `"${key}" needs a number.`;
    if (row.type === "list" && !listItems(row.value).length)
      return `"${key}" needs at least one list item.`;
    const nested = row.error || (row.fields && problem(row.fields));
    if (nested) return `In "${key}": ${nested}`;
  }
  return null;
}

/** A short description of a structured value for its summary line. */
export function describe(value: unknown): string {
  if (value === null || value === undefined) return "Empty";
  if (Array.isArray(value))
    return `${value.length} ${value.length === 1 ? "item" : "items"}`;
  if (typeof value === "object") {
    const count = Object.keys(value).length;
    return `${count} ${count === 1 ? "field" : "fields"}`;
  }
  return String(value);
}
