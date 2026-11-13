import { useState } from "react";
import { api, date, type Job, type JobList } from "../../api";
import { Button, Dialog, ErrorBanner, Field } from "../../design";
import { useFresh } from "../../library/useFresh";
import { useDebounce, useWorkspace } from "../../state";

export type Candidate = Pick<
  Job,
  "id" | "title" | "company" | "location" | "version" | "created_at"
>;

/**
 * Merge two records of one vacancy: the job kept receives the other's
 * observations, notes, files and applications; the other is removed. With a
 * `target` the choice is preset (a likely duplicate); otherwise search for it.
 */
export function MergeDialog({
  job,
  target,
  onClose,
  onMerged,
}: {
  job: Job;
  target?: Candidate | null;
  onClose: () => void;
  /** The id of the job that remains. */
  onMerged: (kept: string) => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [query, setQuery] = useState(target ? "" : job.title);
  const [chosen, setChosen] = useState<string>(target?.id || "");
  const [keepThis, setKeepThis] = useState(false);
  const q = useDebounce(query);
  const found = useFresh<JobList>(
    target ? null : `/jobs?limit=50&q=${encodeURIComponent(q)}`,
    { items: [], total: 0 },
    ["jobs"],
  );
  const options: Candidate[] = target
    ? [target]
    : found.data.items.filter((item) => item.id !== job.id);
  const other = options.find((item) => item.id === chosen);
  async function merge() {
    if (!other) return;
    const [source, kept] = keepThis ? [other, job] : [job, other];
    if (
      await mutate(
        () =>
          api(`/jobs/${source.id}/merge`, "POST", {
            target_id: kept.id,
            expected_version: source.version,
            target_version: kept.version,
          }),
        "Merged. One job now holds both records and their history.",
      )
    )
      onMerged(kept.id);
  }
  return (
    <Dialog
      title="Merge two records of one vacancy?"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            disabled={pending || !other}
            onClick={merge}
          >
            Merge
          </Button>
        </>
      }
    >
      <div className="stack">
        <p>
          The job you keep receives the other record's sources, notes, files and
          applications, so you do not apply twice. Merge only what you have
          checked; nothing is merged without this decision.
        </p>
        {!target && (
          <Field label="Find the other record">
            <input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setChosen("");
              }}
            />
          </Field>
        )}
        {found.error && (
          <ErrorBanner message={found.error} retry={found.reload} />
        )}
        {!target && (
          <Field label="The other record">
            <select
              value={chosen}
              onChange={(event) => setChosen(event.target.value)}
            >
              <option value="">Choose a job</option>
              {options.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.company} · {item.title} · {date(item.created_at)}
                </option>
              ))}
            </select>
          </Field>
        )}
        {other && (
          <fieldset className="choice">
            <legend>Which record stays?</legend>
            <label className="toggle">
              <input
                type="radio"
                name="kept"
                checked={!keepThis}
                onChange={() => setKeepThis(false)}
              />
              <span>
                {other.title} · {other.company}, found {date(other.created_at)}
              </span>
            </label>
            <label className="toggle">
              <input
                type="radio"
                name="kept"
                checked={keepThis}
                onChange={() => setKeepThis(true)}
              />
              <span>
                {job.title} · {job.company}, found {date(job.created_at)} (this
                one)
              </span>
            </label>
          </fieldset>
        )}
      </div>
    </Dialog>
  );
}
