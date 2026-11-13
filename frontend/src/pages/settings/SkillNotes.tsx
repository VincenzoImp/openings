import { useState } from "react";
import { api, type ListResult, type Run } from "../../api";
import { ActorChip, Banner, Button, ErrorBanner, Loading } from "../../design";
import { plural } from "../../library/common";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { useEditorRecord, useUrlState, useWorkspace } from "../../state";
import { appended, type SkillNotes as Notes } from "./model";

const NO_RUNS: ListResult<Run & { method?: string }> = { items: [], total: 0 };

/**
 * The local notes of one skill: the editor, earlier versions to start from,
 * and what recent runs of the workflow said it lacked (their "method"), to
 * add to the notes. Saving makes a new version; nothing is lost.
 */
export function SkillNotes({ skill }: { skill: string }) {
  const path = `/skills/${skill}/notes`;
  const notes = useFresh<Notes | null>(path, null, ["skills"]);
  const record = useEditorRecord(notes.data ?? undefined, path);
  if (notes.error)
    return <ErrorBanner message={notes.error} retry={notes.reload} />;
  if (!record) return <Loading label="Loading the local notes…" />;
  return <NotesForm key={record.version} notes={record} />;
}

function NotesForm({ notes }: { notes: Notes }) {
  const { mutate, pending } = useWorkspace();
  const [draft, setDraft] = useState(notes.text);
  const [history, setHistory] = useState(false);
  const [fromRun, setFromRun] = useUrlState("from_run", "");
  const runs = useFresh(
    `/runs?workflow=${encodeURIComponent(notes.skill)}&status=finished&limit=20`,
    NO_RUNS,
    ["runs"],
  );
  const suggested = runs.data.items
    .filter((run) => run.method?.trim())
    .slice(0, 3);
  const asked = useFresh<Run | null>(
    fromRun ? `/runs/${fromRun}?changes_limit=1` : null,
    null,
    ["runs"],
  );
  const method = asked.data?.report?.method?.trim();
  const over = draft.length > notes.max_length;
  const earlier = notes.versions.filter(
    (item) => item.version !== notes.version,
  );
  const add = (text: string) => setDraft((current) => appended(current, text));
  return (
    <form
      className="stack"
      aria-labelledby="notes-title"
      onSubmit={(event) => {
        event.preventDefault();
        void mutate(
          () =>
            api(`/skills/${notes.skill}/notes`, "PUT", {
              expected_version: notes.version,
              text: draft,
            }),
          draft.trim()
            ? "Local notes saved. Your agent reads them with the skill."
            : "Local notes cleared.",
        );
      }}
    >
      <div className="spread">
        <h3 id="notes-title">Local notes</h3>
        <span className="caption">
          {notes.version ? (
            <>
              Version {notes.version} · changed {dayTime(notes.updated_at)} by{" "}
              <ActorChip actor={notes.updated_by} />
            </>
          ) : (
            "No notes yet"
          )}
        </span>
      </div>
      {fromRun &&
        (asked.loading ? (
          <Loading label="Loading the run's method…" />
        ) : method ? (
          <Banner
            tone="info"
            title={`What the ${asked.data!.workflow} run of ${dayTime(asked.data!.started_at)} lacked`}
            action={
              <>
                <Button
                  size="sm"
                  type="button"
                  data-dirty-control="true"
                  onClick={() => {
                    add(method);
                    setFromRun("");
                  }}
                >
                  Add to the notes
                </Button>
                <Button
                  size="sm"
                  variant="quiet"
                  type="button"
                  onClick={() => setFromRun("")}
                >
                  Dismiss
                </Button>
              </>
            }
          >
            <p className="prose">{method}</p>
          </Banner>
        ) : (
          <Banner
            action={
              <Button size="sm" type="button" onClick={() => setFromRun("")}>
                Dismiss
              </Button>
            }
          >
            That run reported nothing in its method section.
          </Banner>
        ))}
      <div className="field">
        <label className="sr" htmlFor="notes-text">
          Local notes for {notes.skill}
        </label>
        <textarea
          id="notes-text"
          name="text"
          rows={6}
          value={draft}
          aria-describedby="notes-count notes-hint"
          aria-invalid={over || undefined}
          onChange={(event) => setDraft(event.target.value)}
        />
        <small
          className={over ? "error" : "hint"}
          id="notes-count"
          aria-live="polite"
        >
          {draft.length} of {notes.max_length} characters
          {over ? ": shorten the notes to save them" : ""}
        </small>
      </div>
      <div className="row">
        <Button
          variant="primary"
          size="sm"
          disabled={pending || over || draft === notes.text}
        >
          Save notes
        </Button>
        {!!earlier.length && (
          <Button
            type="button"
            size="sm"
            variant="quiet"
            aria-expanded={history}
            onClick={() => setHistory(!history)}
          >
            {history
              ? "Hide earlier versions"
              : `Earlier versions (${notes.versions_total - 1})`}
          </Button>
        )}
        <span className="caption" id="notes-hint">
          Added after the skill's text each time your agent reads it, here and
          in no other workspace. Lasting preferences belong in your{" "}
          <a href="#preferences">Preferences</a>.
        </span>
      </div>
      {history && (
        <ul className="list versions" aria-label="Earlier versions">
          {earlier.map((item) => (
            <li key={item.version}>
              <div className="grow">
                <span className="title">Version {item.version}</span>
                <div className="meta">
                  {dayTime(item.created_at)} by{" "}
                  <ActorChip actor={item.created_by} />
                </div>
                <p className="prose meta">
                  {item.text || "Empty: notes cleared"}
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                data-dirty-control="true"
                onClick={() => setDraft(item.text)}
              >
                Use this text
              </Button>
            </li>
          ))}
        </ul>
      )}
      {!!suggested.length && (
        <section className="stack" aria-labelledby="suggested-title">
          <h4 id="suggested-title">Suggested by recent runs</h4>
          <p className="caption">
            What {plural(suggested.length, "recent run")} of {notes.skill}{" "}
            reported the workflow lacked. Add what applies to this workspace;
            report the rest to the maintainer of the skills.
          </p>
          <ul className="list versions">
            {suggested.map((run) => (
              <li key={run.id}>
                <div className="grow">
                  <a
                    className="title"
                    href={`#activity?section=runs&run=${run.id}`}
                  >
                    {dayTime(run.started_at)}
                  </a>{" "}
                  <ActorChip actor={run.actor} />
                  <p className="prose meta">{run.method}</p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  data-dirty-control="true"
                  onClick={() => add(run.method || "")}
                >
                  Add to the notes
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </form>
  );
}
