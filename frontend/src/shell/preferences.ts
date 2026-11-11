// Theme and density: chosen by the owner, remembered in this browser, applied
// to <html> before the first paint. With nothing stored, the theme follows the
// system and the density is comfortable.

export type Theme = "light" | "dark";
export type Density = "comfortable" | "compact";
export const THEME_KEY = "openings-theme";
export const DENSITY_KEY = "openings-density";

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
export function initialDensity(store: Store | null = storage()): Density {
  return read(store, DENSITY_KEY) === "compact" ? "compact" : "comfortable";
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
export function applyDensity(density: Density, persist = true) {
  const root = document.documentElement;
  if (density === "compact") root.dataset.density = "compact";
  else delete root.dataset.density;
  if (persist) remember(DENSITY_KEY, density);
}
/** Called once before React renders, so the first paint has the right look. */
export function applyStoredPreferences() {
  applyTheme(initialTheme(), false);
  applyDensity(initialDensity(), false);
}
