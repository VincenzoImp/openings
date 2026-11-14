// Words and pure helpers of the Templates screen, kept free of React.
import type { TemplateKind } from "../../query/templates";

export const KINDS: { kind: TemplateKind; label: string }[] = [
  { kind: "cv", label: "CV" },
  { kind: "letter", label: "Letter" },
];
export const kindLabel = (kind: string) =>
  kind === "letter" ? "Letter" : "CV";

export const TABS = [
  { id: "preview", label: "Preview" },
  { id: "source", label: "Source" },
  { id: "files", label: "Files" },
  { id: "limits", label: "Limits" },
] as const;
export type Tab = (typeof TABS)[number]["id"];
export const tabOf = (value: string | null): Tab =>
  TABS.some((tab) => tab.id === value) ? (value as Tab) : "preview";

/** The typed limits of a template; any other rule is kept as it is. */
export const LIMITS = [
  { key: "max_pages", label: "Pages", unit: "pages", max: 20 },
  { key: "max_bullets", label: "Bullets per entry", unit: "bullets", max: 50 },
  {
    key: "max_bullet_chars",
    label: "Bullet length",
    unit: "characters",
    max: 2000,
  },
] as const;
export type LimitKey = (typeof LIMITS)[number]["key"];

/** A limit as written in a rules object: a positive whole number, or none. */
export function limitOf(
  rules: Record<string, unknown> | null | undefined,
  key: LimitKey,
) {
  const value = rules?.[key];
  return typeof value === "number" && Number.isInteger(value) && value > 0
    ? value
    : null;
}

/** "3 characters" / "No limit" */
export function limitText(value: number | null, unit: string) {
  if (value === null) return null;
  return `${value.toLocaleString("en")} ${value === 1 ? unit.replace(/s$/, "") : unit}`;
}

/**
 * The rules after an edit of the limits: typed limits replaced (an empty
 * field removes one), every other key (engine, date_format…) kept.
 */
export function withLimits(
  rules: Record<string, unknown> | null | undefined,
  limits: Record<LimitKey, string>,
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...(rules ?? {}) };
  for (const { key } of LIMITS) {
    const text = limits[key].trim();
    if (!text) delete next[key];
    else next[key] = Number(text);
  }
  return next;
}

/** Whether a typed limit is valid: empty, or a whole number from 1 to max. */
export function limitError(text: string, max: number) {
  const value = text.trim();
  if (!value) return null;
  const number = Number(value);
  return Number.isInteger(number) && number >= 1 && number <= max
    ? null
    : `Give a whole number from 1 to ${max}, or leave it empty.`;
}

/** The other rules of a template, shown read-only: engine, date format… */
export function otherRules(rules: Record<string, unknown> | null | undefined) {
  return Object.entries(rules ?? {})
    .filter(([key]) => !LIMITS.some((limit) => limit.key === key))
    .map(([key, value]) => ({
      label: key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()),
      value: typeof value === "string" ? value : JSON.stringify(value),
    }));
}

/** The kind a TeX file is for, from its name. */
export function kindOfFile(name: string): TemplateKind {
  return /letter|cover|anschreiben|lettre/i.test(name) ? "letter" : "cv";
}

/** A template's name from a file name: "my-cv_2024.tex" → "My cv 2024". */
export function nameOfFile(name: string) {
  const base = name
    .replace(/\.[^.]+$/, "")
    .replace(/[-_]+/g, " ")
    .trim();
  return base ? base[0].toUpperCase() + base.slice(1) : "Uploaded template";
}

/** "X copy", or "X copy 2" when that name is taken. */
export function copyName(name: string, taken: string[]) {
  const names = new Set(taken);
  let candidate = `${name} copy`;
  for (let n = 2; names.has(candidate); n++) candidate = `${name} copy ${n}`;
  return candidate;
}

/** The kind of a template file, for its row. */
export function fileKind(file: { name: string; media_type: string }) {
  if (file.media_type === "application/pdf" || /\.pdf$/i.test(file.name))
    return "PDF";
  if (/\.(cls|sty)$/i.test(file.name)) return "Class file";
  if (/\.(tex|ltx)$/i.test(file.name)) return "LaTeX";
  if (
    /\.(otf|ttf|woff2?)$/i.test(file.name) ||
    file.media_type.startsWith("font/")
  )
    return "Font";
  if (file.media_type.startsWith("image/")) return "Image";
  return "File";
}

/** A file size in B, KB or MB. */
export function fileSize(bytes: number) {
  if (bytes < 1000) return `${bytes} B`;
  if (bytes < 1_000_000) return `${Math.round(bytes / 100) / 10} KB`;
  return `${Math.round(bytes / 100_000) / 10} MB`;
}

export const isPdf = (file: { name: string; media_type: string }) =>
  fileKind(file) === "PDF";

/** "Changed 3h ago", "Changed yesterday", "Changed 13 Nov". */
export function changedText(relative: string) {
  if (/^\d+[mhd]$/.test(relative)) return `Changed ${relative} ago`;
  if (relative === "Just now" || relative === "Yesterday")
    return `Changed ${relative.toLowerCase()}`;
  return `Changed ${relative}`;
}

/** Source text as shown: without the final newline of the file. */
export const shownSource = (tex: string) => tex.replace(/\n$/, "");
