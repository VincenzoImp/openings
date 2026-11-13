// Class names of the design system's components, kept apart from React so
// they can be tested without a browser.

/** Join class names, dropping empty and repeated ones. */
export function cx(...names: (string | false | null | undefined)[]) {
  const seen = new Set<string>();
  for (const name of names)
    if (name) for (const part of name.split(/\s+/)) if (part) seen.add(part);
  return [...seen].join(" ");
}

/**
 * Classes of a button: `variant` and `className` may hold several names;
 * `md` is the default size and adds none.
 */
export function buttonClass(
  variant = "",
  size = "",
  className = "",
  iconOnly = false,
) {
  return cx(
    iconOnly ? "icon-btn" : "btn",
    variant,
    size === "md" ? "" : size,
    className,
  );
}

export type Tone =
  "neutral" | "ready" | "attention" | "danger" | "info" | "agent";

/** Classes of a tag; the neutral tone adds none. */
export function tagClass(tone: Tone = "neutral", className = "") {
  return cx("tag", tone === "neutral" ? "" : tone, className);
}
