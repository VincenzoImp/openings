import { useCallback, useState } from "react";

/** Cursor over a list of `count` items; clamps when the list shrinks. */
export function useSelection(count: number) {
  const [raw, setRaw] = useState(0);
  const index = count === 0 ? -1 : Math.min(raw, count - 1);
  const setIndex = useCallback((value: number) => setRaw(Math.max(0, value)), []);
  const next = useCallback(
    () => setRaw((current) => Math.min(Math.max(count - 1, 0), current + 1)),
    [count],
  );
  const prev = useCallback(() => setRaw((current) => Math.max(0, current - 1)), []);
  return { index, setIndex, next, prev };
}
