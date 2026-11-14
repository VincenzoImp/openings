// The keys of the Jobs screen, before the shell's: a key handled here is
// not read again by the shell (`/` searches this list instead of opening ⌘K).
import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";
import { isModKey, isTyping } from "../../ui/keys";
import type { Selection } from "../../ui/List";
import { fetchJob, type BulkAction } from "./data";
import type { Job, JobSummary } from "./model";

/** What the keys act on, as the screen has it at this render. */
export interface JobKeys {
  active: string;
  current?: JobSummary;
  pickedJobs: JobSummary[];
  move: (step: number, focusRow: boolean) => void;
  decide: (jobs: JobSummary[], to: BulkAction) => Promise<void>;
  undo: () => void;
  picked: Selection;
  ids: string[];
  wide: boolean;
  open: boolean;
  openJob: (id: string) => void;
  close: () => void;
  phone: boolean;
  setCorrecting: (job: Job) => void;
}

/**
 * `j`/`k` and the arrows move, Shift+J/K extend the selection, `x` picks,
 * `s`/`d`/`r` decide, `z` and ⌘Z undo, `o` opens the posting, `e` corrects,
 * Enter opens, `/` searches and Esc clears or closes. The listener is bound
 * once and reads the latest state.
 */
export function useJobKeys(
  state: JobKeys,
  searchRef: RefObject<HTMLInputElement | null>,
) {
  const latest = useRef(state);
  useLayoutEffect(() => {
    latest.current = state;
  });
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (document.querySelector("dialog[open]")) return;
      const state = latest.current;
      const target = event.target as HTMLElement;
      const consume = () => {
        event.preventDefault();
        event.stopPropagation();
      };
      if (event.altKey) return;
      if (isModKey(event)) {
        if (
          event.key.toLowerCase() === "z" &&
          !event.shiftKey &&
          !isTyping(target)
        ) {
          consume();
          state.undo();
        }
        return;
      }
      if (isTyping(target)) {
        if (event.key === "Escape" && target === searchRef.current) {
          consume();
          target.blur();
        }
        return;
      }
      if (target.closest?.("[role=menu], [popover], [role=tablist]")) return;
      const inList = !!target.closest?.(".jobs-list");
      const neutral =
        inList || target === document.body || target.id === "content";
      const job = state.current;
      const many = state.pickedJobs;
      switch (event.key) {
        case "j":
        case "k":
          consume();
          return state.move(event.key === "j" ? 1 : -1, inList || neutral);
        case "ArrowDown":
        case "ArrowUp":
          if (!neutral) return;
          consume();
          return state.move(event.key === "ArrowDown" ? 1 : -1, true);
        case "J":
        case "K": {
          consume();
          const step = event.key === "J" ? 1 : -1;
          const index = state.ids.indexOf(state.active);
          const next = state.ids[index + step];
          if (!state.picked.ids.size && state.active)
            state.picked.toggle(state.active);
          if (next) {
            state.picked.extend(state.ids, next);
            state.move(step, inList || neutral);
          }
          return;
        }
        case "x":
          if (!state.active) return;
          consume();
          return state.picked.toggle(state.active);
        case "s":
        case "d":
        case "r": {
          const to: BulkAction =
            event.key === "s"
              ? "shortlisted"
              : event.key === "d"
                ? "dismissed"
                : "new";
          const from = to === "new" ? "dismissed" : "new";
          const jobs = (many.length ? many : job ? [job] : []).filter(
            (item) => item.triage === from,
          );
          if (!jobs.length) return;
          consume();
          return void state.decide(jobs, to);
        }
        case "z":
          consume();
          return state.undo();
        case "o":
          if (!job?.url) return;
          consume();
          window.open(job.url, "_blank", "noopener,noreferrer");
          return;
        case "e":
          if (!job) return;
          consume();
          return void fetchJob(job.id).then(
            state.setCorrecting,
            () => undefined,
          );
        case "Enter":
          if (!neutral || !state.active) return;
          consume();
          if (state.wide) document.getElementById("job-title")?.focus();
          else state.openJob(state.active);
          return;
        case "/":
          // On a phone, and while the bulk bar hides the search, `/` is
          // the shell's search.
          if (state.phone || !searchRef.current) return;
          consume();
          searchRef.current.focus();
          return;
        case "Escape":
          if (state.picked.ids.size) {
            consume();
            state.picked.clear();
          } else if (!state.wide && state.open) {
            consume();
            state.close();
          }
          return;
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [searchRef]);
}
