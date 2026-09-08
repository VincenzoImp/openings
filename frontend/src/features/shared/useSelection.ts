import { useCallback, useMemo, useState } from "react";

/**
 * A cursor over a list plus a set of checked ids for bulk actions. The
 * cursor clamps when the list shrinks; the checked set is trimmed to ids
 * that are still present.
 */
export function useSelection(ids: string[]) {
  const [raw, setRaw] = useState(0);
  const [checkedIds, setChecked] = useState<Set<string>>(() => new Set());
  const count = ids.length;
  const index = count === 0 ? -1 : Math.min(raw, count - 1);
  const currentId = index >= 0 ? ids[index] : null;

  const setIndex = useCallback((value: number) => setRaw(Math.max(0, value)), []);
  const next = useCallback(
    () => setRaw((current) => Math.min(Math.max(count - 1, 0), current + 1)),
    [count],
  );
  const prev = useCallback(() => setRaw((current) => Math.max(0, current - 1)), []);

  const present = useMemo(() => new Set(ids), [ids]);
  const checked = useMemo(
    () => new Set(Array.from(checkedIds).filter((id) => present.has(id))),
    [checkedIds, present],
  );

  const toggle = useCallback((id: string) => {
    setChecked((current) => {
      const copy = new Set(current);
      if (copy.has(id)) {
        copy.delete(id);
      } else {
        copy.add(id);
      }
      return copy;
    });
  }, []);
  const toggleCurrent = useCallback(() => {
    if (currentId) {
      toggle(currentId);
    }
  }, [currentId, toggle]);
  const checkAll = useCallback(() => setChecked(new Set(ids)), [ids]);
  const clear = useCallback(() => setChecked(new Set()), []);
  const extendTo = useCallback(
    (to: number) => {
      const from = index;
      const [start, end] = from < to ? [from, to] : [to, from];
      setChecked((current) => {
        const copy = new Set(current);
        for (const id of ids.slice(Math.max(0, start), end + 1)) {
          copy.add(id);
        }
        return copy;
      });
      setRaw(Math.max(0, to));
    },
    [ids, index],
  );

  return {
    index,
    currentId,
    setIndex,
    next,
    prev,
    checked,
    toggle,
    toggleCurrent,
    checkAll,
    clear,
    extendTo,
    /** The ids an action applies to: the checked set, else the cursor. */
    targets: checked.size > 0 ? Array.from(checked) : currentId ? [currentId] : [],
  };
}
