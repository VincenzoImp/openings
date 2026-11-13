// The colour theme: the system's, or a fixed light or dark one, kept on
// <html data-theme> and remembered in the browser.

export type ThemeMode = "system" | "light" | "dark";
/** The key the current dashboard already uses, so the choice carries over. */
export const THEME_KEY = "openings-theme";

export function readTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(mode: ThemeMode, remember = true) {
  const root = document.documentElement;
  if (mode === "system") delete root.dataset.theme;
  else root.dataset.theme = mode;
  if (!remember) return;
  try {
    if (mode === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, mode);
  } catch {
    // Private windows may refuse storage; the theme still applies.
  }
}
