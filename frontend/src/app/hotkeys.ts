import { useEffect, useRef } from "react";

export type HotkeyHandler = (event: KeyboardEvent) => void;

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

/**
 * Bind single-key shortcuts while the component is mounted. Keys are matched
 * on `event.key` ("j", "?", "Escape", "Enter"); chords with Ctrl/Meta/Alt are
 * never intercepted so the browser keeps its own shortcuts.
 */
export function useHotkeys(bindings: Record<string, HotkeyHandler>, enabled = true): void {
  const latest = useRef(bindings);
  useEffect(() => {
    latest.current = bindings;
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey || event.defaultPrevented) {
        return;
      }
      const handler = latest.current[event.key];
      if (!handler) {
        return;
      }
      if (event.key !== "Escape" && isTypingTarget(event.target)) {
        return;
      }
      event.preventDefault();
      handler(event);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}
