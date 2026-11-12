// What collection did since a moment, from its newest runs. No React.
import type { CollectionRun } from "../../api";

const plural = (count: number, one: string) =>
  `${count} ${count === 1 ? one : one + "s"}`;

export interface Collected {
  /** Collection runs since the moment asked about. */
  runs: number;
  created: number;
  /** Sources that brought new jobs. */
  sources: string[];
  /** Sources whose latest run since then failed. */
  failed: string[];
}
const key = (run: CollectionRun) => run.source_id || run.source_name;
/** What collection did since `since`, from its newest runs (newest first). */
export function collectedSince(
  runs: CollectionRun[],
  since: string,
): Collected {
  const from = Date.parse(since);
  const recent = runs.filter(
    (run) => Date.parse(run.finished_at || run.created_at) >= from,
  );
  const sources = new Set<string>(),
    latest = new Map<string, string>();
  let created = 0;
  for (const run of recent) {
    const found = run.counts?.created || 0;
    created += found;
    if (found) sources.add(run.source_name);
    // A run outlives its source: the name stands in for a deleted one.
    if (!latest.has(key(run))) latest.set(key(run), run.state);
  }
  const failed = new Set(
    recent
      .filter((run) => latest.get(key(run)) === "failed")
      .map((run) => run.source_name),
  );
  return {
    runs: recent.length,
    created,
    sources: [...sources],
    failed: [...failed],
  };
}
/** "61 new jobs from 9 sources; 1 source failed: Example board". */
export function collectedLine(collected: Collected) {
  const found = collected.created
    ? `${plural(collected.created, "new job")} from ${plural(collected.sources.length, "source")}`
    : `No new jobs in ${plural(collected.runs, "collection run")}`;
  if (!collected.failed.length) return found;
  const names = collected.failed.slice(0, 3).join(", ");
  const more = collected.failed.length - 3;
  return `${found}; ${plural(collected.failed.length, "source")} failed: ${names}${more > 0 ? ` and ${more} more` : ""}`;
}
