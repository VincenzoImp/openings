// The colour theme: System, Light or Dark, remembered in this browser.
// <html data-theme> holds the theme in effect (System resolved to light or
// dark), and the theme-color meta follows its background.
import { useCallback, useEffect, useState } from "react";

export type ThemeMode = "system" | "light" | "dark";
export const THEME_KEY = "openings-theme";

const DARK = "(prefers-color-scheme: dark)";
const CHANGED = "openings:theme";

export function readTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

/** The theme in effect for a choice and the system's preference. */
export function resolveTheme(
  mode: ThemeMode,
  systemDark: boolean,
): "light" | "dark" {
  return mode === "system" ? (systemDark ? "dark" : "light") : mode;
}

/** Show a theme, without remembering it. */
export function applyTheme(mode: ThemeMode) {
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
  applyTheme(readTheme());
}

/** The theme chosen in this browser, and a setter that applies it. */
export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(readTheme);
  useEffect(() => {
    applyTheme(mode);
    if (mode !== "system") return;
    const media = matchMedia(DARK);
    const follow = () => applyTheme("system");
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
