// The global keyboard: `g` then a letter goes to a screen, `n` adds a job,
// `/` and ⌘K search, `?` shows the shortcut sheet. Pure, so it is tested
// directly; the shell binds it (Shell.tsx). A screen's own keys (j/k, s, d…)
// come first: a key the screen handled (defaultPrevented) is not read here.
import type { RouteId } from "./routes";

export type ShellAction =
  | { kind: "go"; route: RouteId }
  | { kind: "add-job" }
  | { kind: "search" }
  | { kind: "help" };

/** `g` + letter. */
export const GO: Record<string, RouteId> = {
  t: "today",
  j: "jobs",
  a: "applications",
  p: "profile",
};

/** How long `g` waits for its second key. */
export const CHORD_MS = 1200;

/**
 * What a key does after the previous one: an action, or `pending` while a
 * chord (`g`) waits for its second key. Keys are plain (no modifier).
 */
export function readKey(
  key: string,
  pending: string | null,
): { action: ShellAction | null; pending: string | null } {
  if (pending === "g") {
    const route = GO[key.toLowerCase()];
    return { action: route ? { kind: "go", route } : null, pending: null };
  }
  switch (key) {
    case "g":
      return { action: null, pending: "g" };
    case "n":
      return { action: { kind: "add-job" }, pending: null };
    case "/":
      return { action: { kind: "search" }, pending: null };
    case "?":
      return { action: { kind: "help" }, pending: null };
    default:
      return { action: null, pending: null };
  }
}

/** The shortcut sheet: the keys of the shell and of the lists. */
export const SHEET: { title: string; items: [string[], string][] }[] = [
  {
    title: "Anywhere",
    items: [
      [["⌘", "K"], "Search and commands"],
      [["/"], "Search"],
      [["n"], "Add a job"],
      [["g", "t"], "Go to Today"],
      [["g", "j"], "Go to Jobs"],
      [["g", "a"], "Go to Applications"],
      [["g", "p"], "Go to Profile"],
      [["?"], "Keyboard shortcuts"],
    ],
  },
  {
    title: "Lists",
    items: [
      [["j"], "Next"],
      [["k"], "Previous"],
      [["↵"], "Open"],
      [["x"], "Select"],
      [["⇧", "J"], "Select the next one too"],
      [["⇧", "click"], "Select a range"],
      [["Esc"], "Clear the selection"],
      [["⌘", "Z"], "Undo"],
    ],
  },
  {
    title: "Jobs",
    items: [
      [["s"], "Shortlist"],
      [["d"], "Dismiss"],
      [["r"], "Restore a dismissed job"],
      [["e"], "Correct details"],
      [["o"], "Open the posting"],
    ],
  },
];
