// Class names of the design system's components, kept apart from React so the
// mapping from older variant names can be tested without a browser.

/** Join class names, dropping empty and repeated ones. */
export function cx(...names: (string | false | null | undefined)[]) {
  const seen = new Set<string>();
  for (const name of names)
    if (name) for (const part of name.split(/\s+/)) if (part) seen.add(part);
  return [...seen].join(" ");
}

// Names the pages written before the design system still pass.
const buttonAliases: Record<string, string> = {
  small: "sm",
  subtle: "quiet",
  "danger-fill": "danger",
  default: "",
  md: "",
};

/** Classes of a button: `variant` and `className` may hold several names. */
export function buttonClass(
  variant = "",
  size = "",
  className = "",
  iconOnly = false,
) {
  const names = `${variant} ${size} ${className}`
    .split(/\s+/)
    .map((name) => buttonAliases[name] ?? name);
  return cx(iconOnly ? "icon-btn" : "btn", ...names);
}

export type Tone =
  "neutral" | "ready" | "attention" | "danger" | "info" | "agent";
const toneAliases: Record<string, Tone> = {
  green: "ready",
  amber: "attention",
  neutral: "neutral",
};

/** Classes of a tag; `green` and `amber` are the older names of two tones. */
export function tagClass(tone = "neutral", className = "") {
  const resolved = toneAliases[tone] ?? tone;
  return cx("tag", resolved === "neutral" ? "" : resolved, className);
}
