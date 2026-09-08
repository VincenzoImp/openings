import { createContext, useContext, useEffect, useMemo, useRef } from "react";

/**
 * One keyboard listener for the whole app. Views, dialogs and the shell
 * register bindings in scopes; the innermost scope wins. The registry also
 * feeds the Help dialog, so the shortcut list never drifts from reality.
 */

export type HotkeyScope = "global" | "view" | "dialog";
export const SCOPE_ORDER: HotkeyScope[] = ["dialog", "view", "global"];

export interface HotkeyBinding {
  key: string;
  run: (event: KeyboardEvent) => void;
  description?: string;
  group?: string;
  /** Keys that are shown together in the help (e.g. "j / k"). */
  label?: string;
}

export interface ShortcutEntry {
  group: string;
  label: string;
  description: string;
}

export interface HotkeyRegistry {
  /** Stable for the provider's lifetime, so effects can depend on it. */
  register: (scope: HotkeyScope, id: string, bindings: HotkeyBinding[]) => () => void;
  list: () => ShortcutEntry[];
  /** Bumped on every (un)registration; the help dialog re-reads the list. */
  version: number;
}

export const HotkeyContext = createContext<HotkeyRegistry | null>(null);

/** Keys typed into a field belong to the field, except Escape. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable ||
    target.getAttribute("role") === "textbox"
  );
}

let counter = 0;

/**
 * Bind keys while the component is mounted. Handlers always see the latest
 * render through a ref, so callers can pass inline closures.
 */
export function useHotkeys(scope: HotkeyScope, bindings: HotkeyBinding[], enabled = true): void {
  const register = useContext(HotkeyContext)?.register;
  const latest = useRef(bindings);
  const id = useRef<string | null>(null);
  if (id.current === null) {
    id.current = `hk-${++counter}`;
  }
  useEffect(() => {
    latest.current = bindings;
  });
  const signature = bindings.map((binding) => binding.key).join("|");
  useEffect(() => {
    if (!register || !enabled) {
      return;
    }
    const proxies = latest.current.map((binding) => ({
      ...binding,
      run: (event: KeyboardEvent) =>
        latest.current.find((entry) => entry.key === binding.key)?.run(event),
    }));
    return register(scope, id.current as string, proxies);
    // Re-register when the set of keys changes (signature), not on every render.
  }, [register, scope, enabled, signature]);
}

export function useShortcutList(): ShortcutEntry[] {
  const registry = useContext(HotkeyContext);
  const version = registry?.version ?? 0;
  return useMemo(() => registry?.list() ?? [], [registry, version]);
}
