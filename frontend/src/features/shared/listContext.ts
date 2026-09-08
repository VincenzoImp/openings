/** The ids of the list a job page was opened from, so it can step to the neighbours. */

const KEY = "openings.last-list";

export function rememberList(ids: string[]): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(ids.slice(0, 2000)));
  } catch {
    // nothing to remember without storage
  }
}

export function recallList(): string[] {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}
