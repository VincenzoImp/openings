// The theme: System, Light or Dark, remembered in this browser. <html
// data-theme> always holds the theme in effect (System resolved to light or
// dark), because the old stylesheet of the screens not yet rebuilt reads only
// the attribute; the design system reads both.
import { useCallback, useEffect, useState } from "react";
import { THEME_KEY, readTheme, type ThemeMode } from "../ui/theme";

const DARK = "(prefers-color-scheme: dark)";
const CHANGED = "openings:theme";

/** The theme in effect for a choice and the system's preference. */
export function resolveTheme(
  mode: ThemeMode,
  systemDark: boolean,
): "light" | "dark" {
  return mode === "system" ? (systemDark ? "dark" : "light") : mode;
}

function apply(mode: ThemeMode) {
  const root = document.documentElement;
  root.dataset.theme = resolveTheme(
    mode,
    globalThis.matchMedia?.(DARK).matches ?? false,
  );
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute(
      "content",
      getComputedStyle(root).getPropertyValue("--bg").trim(),
    );
}

function remember(mode: ThemeMode) {
  try {
    if (mode === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, mode);
  } catch {
    // Storage can be refused; the choice then lasts for this page.
  }
}

/** Before the first paint, so the page never flashes the other theme. */
export function applyStoredTheme() {
  apply(readTheme());
}

/** The account menu's theme: the choice, and a setter that applies it. */
export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(readTheme);
  useEffect(() => {
    apply(mode);
    if (mode !== "system") return;
    const media = matchMedia(DARK);
    const follow = () => apply("system");
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, [mode]);
  // The account menu and Settings › Account choose the same theme.
  useEffect(() => {
    const follow = () => setMode(readTheme());
    window.addEventListener(CHANGED, follow);
    return () => window.removeEventListener(CHANGED, follow);
  }, []);
  const choose = useCallback((next: ThemeMode) => {
    remember(next);
    setMode(next);
    window.dispatchEvent(new Event(CHANGED));
  }, []);
  return [mode, choose] as const;
}
