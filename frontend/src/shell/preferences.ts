// Theme: chosen by the owner, remembered in this browser, applied to <html>
// before the first paint. With nothing stored, the theme follows the system.

export type Theme = "light" | "dark";
export const THEME_KEY = "openings-theme";

interface Store {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}
function storage(): Store | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}
function read(store: Store | null, key: string) {
  try {
    return store?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export function initialTheme(
  store: Store | null = storage(),
  systemDark = globalThis.matchMedia?.("(prefers-color-scheme: dark)")
    .matches ?? false,
): Theme {
  const saved = read(store, THEME_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return systemDark ? "dark" : "light";
}

function remember(key: string, value: string) {
  try {
    storage()?.setItem(key, value);
  } catch {
    // Storage can be unavailable; the choice then lasts for this page only.
  }
}
/** Apply and remember the theme; the browser chrome follows the shell colour. */
export function applyTheme(theme: Theme, persist = true) {
  const root = document.documentElement;
  root.dataset.theme = theme;
  if (persist) remember(THEME_KEY, theme);
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", getComputedStyle(root).getPropertyValue("--bg"));
}
/** Called once before React renders, so the first paint has the right look. */
export function applyStoredPreferences() {
  applyTheme(initialTheme(), false);
}
