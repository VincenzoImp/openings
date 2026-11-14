// The setup checklist: what a workspace still lacks, read from server facts
// only (never from browser storage), so every browser shows the same state.
// No React and no imports: tested directly (tests/today.test.mjs).

/** The server facts setup depends on; numbers are totals. */
export interface SetupFacts {
  /** The Profile's name, trimmed. */
  name: string;
  /** Items in all Preferences sections together. */
  preferences: number;
  sources: number;
  jobs: number;
  /** Career entries, highlights and templates together. */
  cv: number;
}

export type SetupStep = "about" | "jobs" | "cv";

export interface ChecklistItem {
  step: SetupStep;
  title: string;
  /** The button that does it. */
  action: string;
  done: boolean;
}

/** The three things a workspace needs, in the order to do them. */
export function checklist(facts: SetupFacts): ChecklistItem[] {
  return [
    {
      step: "about",
      title: "Tell us what you're looking for",
      action: "Start",
      done: Boolean(facts.name) && facts.preferences > 0,
    },
    {
      step: "jobs",
      title: "Add a job source or a job",
      action: "Add jobs",
      done: facts.sources > 0 || facts.jobs > 0,
    },
    {
      step: "cv",
      title: "Add your CV",
      action: "Add your CV",
      done: facts.cv > 0,
    },
  ];
}

/** How far setup is: "1 of 3 done", and whether nothing is left. */
export function progress(facts: SetupFacts) {
  const items = checklist(facts);
  const done = items.filter((item) => item.done).length;
  return {
    items,
    done,
    total: items.length,
    finished: done === items.length,
    /** Nothing at all yet: a brand new workspace. */
    empty: done === 0 && !facts.name,
  };
}
