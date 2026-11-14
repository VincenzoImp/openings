// The writes of Preferences. Every change of a section sends the whole
// section with its version (preferences_update). Changes run one after the
// other, each on the section as the previous one left it, and show at once;
// a change that meets a newer version is dropped, the section is read again
// and says so, and an open editor keeps its text.
import { useCallback, useRef, useState } from "react";
import { isConflict } from "../../query/mutation";
import {
  useSectionWrite,
  type Section,
  type SectionName,
  type Statement,
} from "../../query/preferences";
import { itemsBody } from "./model";

type Change = (items: Statement[]) => Statement[];
export type Outcome = "ok" | "conflict" | "error";

interface Base {
  version: number;
  items: Statement[];
}

export function useStatements(sections: Section[] | undefined) {
  const latest = useRef(new Map<SectionName, Base>());
  // Keep the newest version known: the server's, or the last save's answer.
  for (const section of sections ?? []) {
    const name = section.section as SectionName;
    const known = latest.current.get(name);
    if (!known || section.version >= known.version)
      latest.current.set(name, {
        version: section.version,
        items: section.items as Statement[],
      });
  }
  const [shown, setShown] = useState<Partial<Record<SectionName, Statement[]>>>(
    {},
  );
  const [conflicts, setConflicts] = useState<ReadonlySet<SectionName>>(
    () => new Set(),
  );
  const [error, setError] = useState<string | null>(null);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const waiting = useRef(new Map<SectionName, number>());
  const write = useSectionWrite();

  const itemsOf = useCallback(
    (name: SectionName) => shown[name] ?? latest.current.get(name)?.items ?? [],
    [shown],
  );

  /** Apply a change now and save it after the ones before it. */
  const change = useCallback(
    (section: SectionName, apply: Change): Promise<Outcome> => {
      setShown((current) => ({
        ...current,
        [section]: apply(
          current[section] ?? latest.current.get(section)?.items ?? [],
        ),
      }));
      setConflicts((current) => {
        if (!current.has(section)) return current;
        const next = new Set(current);
        next.delete(section);
        return next;
      });
      setError(null);
      waiting.current.set(section, (waiting.current.get(section) ?? 0) + 1);
      const run = queue.current.then(async (): Promise<Outcome> => {
        const base = latest.current.get(section) ?? { version: 0, items: [] };
        let outcome: Outcome = "ok";
        try {
          const result = await write.mutateAsync({
            section,
            version: base.version,
            items: itemsBody(section, apply(base.items)),
          });
          latest.current.set(section, {
            version: result.version,
            items: result.items as Statement[],
          });
        } catch (cause) {
          outcome = isConflict(cause) ? "conflict" : "error";
          if (outcome === "conflict")
            setConflicts((current) => new Set(current).add(section));
          else
            setError(
              cause instanceof Error
                ? cause.message
                : "The change was not saved.",
            );
        }
        const left = (waiting.current.get(section) ?? 1) - 1;
        waiting.current.set(section, left);
        // Once nothing waits, what the server holds is what is shown.
        if (!left || outcome !== "ok")
          setShown((current) => {
            const next = { ...current };
            delete next[section];
            return next;
          });
        return outcome;
      });
      queue.current = run;
      return run;
    },
    [write],
  );

  const settle = useCallback((section: SectionName) => {
    setConflicts((current) => {
      const next = new Set(current);
      next.delete(section);
      return next;
    });
  }, []);

  return {
    itemsOf,
    change,
    conflicts,
    settle,
    error,
    clearError: () => setError(null),
  };
}
