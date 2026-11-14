// The new jobs opened in this browser, for the unread dot of a row. A
// convenience kept in localStorage: without it every new job reads unread.
import { useCallback, useState } from "react";

const KEY = "openings-jobs-seen";
const KEEP = 3000;

function load(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(value)
      ? value.filter((id) => typeof id === "string")
      : [];
  } catch {
    return [];
  }
}

/** Which jobs were opened, and how to mark one. */
export function useSeen() {
  const [seen, setSeen] = useState<ReadonlySet<string>>(() => new Set(load()));
  const mark = useCallback((id: string) => {
    setSeen((current) => {
      if (!id || current.has(id)) return current;
      const next = [...current, id].slice(-KEEP);
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        // Private windows and blocked storage: the dot stays this session.
      }
      return new Set(next);
    });
  }, []);
  return { seen, mark };
}
