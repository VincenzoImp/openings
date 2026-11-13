// Keyboard models of the primitives, free of React so they can be tested.

/**
 * The next index in a vertical list: `j`/ArrowDown and `k`/ArrowUp move one
 * row and stop at the ends; Home and End jump. Null for any other key.
 */
export function listIndex(key: string, index: number, count: number) {
  if (count <= 0) return null;
  const last = count - 1;
  switch (key) {
    case "j":
    case "ArrowDown":
      return index < 0 ? 0 : Math.min(index + 1, last);
    case "k":
    case "ArrowUp":
      return index < 0 ? 0 : Math.max(index - 1, 0);
    case "Home":
      return 0;
    case "End":
      return last;
    default:
      return null;
  }
}

/** The next index in a menu or tab row: arrows wrap; Home and End jump. */
export function cycleIndex(
  key: string,
  index: number,
  count: number,
  orientation: "horizontal" | "vertical" = "vertical",
) {
  if (count <= 0) return null;
  const [back, forward] =
    orientation === "vertical"
      ? ["ArrowUp", "ArrowDown"]
      : ["ArrowLeft", "ArrowRight"];
  if (key === forward) return index < 0 ? 0 : (index + 1) % count;
  if (key === back) return index < 0 ? count - 1 : (index - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}

/**
 * Typeahead: the first label after `from` that starts with `typed`, wrapping
 * around; -1 when none does. Matching ignores case.
 */
export function typeahead(labels: string[], typed: string, from: number) {
  const query = typed.toLowerCase();
  if (!query) return -1;
  for (let step = 1; step <= labels.length; step++) {
    const index = (from + step + labels.length) % labels.length;
    if (labels[index].toLowerCase().startsWith(query)) return index;
  }
  return -1;
}

/** Whether a key press belongs to a text field rather than to a shortcut. */
export function isTyping(target: EventTarget | null) {
  const el = target as HTMLElement | null;
  if (!el || !el.tagName) return false;
  if (el.isContentEditable) return true;
  if (el.tagName === "TEXTAREA" || el.tagName === "SELECT") return true;
  if (el.tagName !== "INPUT") return false;
  const type = (el as HTMLInputElement).type;
  return !["checkbox", "radio", "button", "submit", "reset", "range"].includes(
    type,
  );
}

/** A shortcut without modifiers: a letter typed outside a text field. */
export function plainKey(event: {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  altKey: boolean;
  target: EventTarget | null;
}) {
  if (event.metaKey || event.ctrlKey || event.altKey) return null;
  if (isTyping(event.target)) return null;
  return event.key;
}

/** ⌘ (or Ctrl on other systems) held with a key, as in ⌘K or ⌘↵. */
export function isModKey(event: { metaKey: boolean; ctrlKey: boolean }) {
  return event.metaKey || event.ctrlKey;
}
