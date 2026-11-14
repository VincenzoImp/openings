import { useEffect, useRef, useState } from "react";
import { ApiError, api, newId, type Application, type Job } from "../../api";
import {
  ActionBar,
  Banner,
  Button,
  Card,
  ErrorBanner,
  Loading,
  Tag,
} from "../../design";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";
import type { Links } from "../../library/records";
import { stageLabels, outcomeLabels } from "../applications/model";
import { reviewHref } from "../applications/links";
import { DismissDialog } from "./DismissDialog";
import { Duplicate } from "./Duplicate";
import { JobMore } from "./JobMore";
import { JobTimeline } from "./JobTimeline";
import { JOB_SCOPES, dismissedBy, signalTags, sourceLabel } from "./model";

const PREVIEW = 1400;

/** The signals of a job, as a list of tags, with what is still unknown. */
function Signals({ job, own }: { job: Job; own: Set<string> | null }) {
  const tags = signalTags(job, { full: true, own });
  const listed = job.postings?.some(
    // Only a company board lists its whole board; a search never says a posting is gone.
    (posting) =>
      !!posting.source_kind &&
      !["jobspy", "rss"].includes(posting.source_kind) &&
      !posting.unlisted_at,
  );
  return (
    <div className="stack signals">
      {tags.length > 0 || listed ? (
        <ul
          className="tag-list"
          aria-label="Signals found when the job was collected"
        >
          {tags.map((tag) => (
            <li key={tag.text}>
              <Tag tone={tag.tone}>{tag.text}</Tag>
            </li>
          ))}
          {listed && !job.signals.no_longer_listed && (
            <li>
              <Tag tone="ready">
                Listed by its source · seen{" "}
                {dayTime(
                  job.postings
                    ?.map((posting) => posting.last_seen_at)
                    .sort()
                    .at(-1),
                ).toLowerCase()}
              </Tag>
            </li>
          )}
        </ul>
      ) : null}
      {!job.signals.computed && (
        <p className="caption">
          Signals of jobs collected before 0.21 are being computed.
        </p>
      )}
    </div>
  );
}

/** The words of what an application holds, from an application_has_work refusal. */
const WORK: Record<string, string> = {
  started_separately: "it was started on its own",
  stage: "it moved past Shortlisted",
  documents: "documents",
  notes: "notes",
  replies: "employer replies",
  requirements: "requirements",
  questions: "form questions",
  answers: "form answers",
};
/** A triage refused because the job's application has work, said in words. */
export function triageError(error: unknown) {
  if (
    error instanceof ApiError &&
    error.code === "application_has_work" &&
    Array.isArray(error.details?.work)
  ) {
    const work = (error.details.work as string[]).map(
      (item) => WORK[item] || item,
    );
    return new ApiError(
      `The application of this job has work in it (${work.join(", ")}), so it stays shortlisted. Close or delete the application first.`,
      error.status,
      error.code,
      error.path,
      error.details,
    );
  }
  return error;
}

/**
 * Shortlist (which starts the application) and dismiss a new job; open the
 * application of a shortlisted one; restore a dismissed one. On a narrow
 * screen they stay in a bar above the bottom navigation.
 */
function Actions({
  job,
  onOpenApplication,
  onNote,
  leaving,
}: {
  job: Job;
  onOpenApplication: (id: string) => void;
  onNote: () => void;
  leaving: (id: string) => (() => void) | null;
}) {
  const { mutate, pending } = useWorkspace();
  const [dismissing, setDismissing] = useState(false);
  const key = useRef<string | null>(null);
  async function triage(value: string, message: string, reason?: string) {
    // In New and Shortlisted the job leaves the list: show the next.
    const next = leaving(job.id);
    const ok = await mutate(async () => {
      try {
        await api(`/jobs/${job.id}/triage`, "POST", {
          triage: value,
          expected_version: job.version,
          ...(reason ? { reason } : {}),
        });
      } catch (error) {
        throw triageError(error);
      }
    }, message);
    if (ok) next?.();
    return ok;
  }
  /** A new application for a shortlisted job whose applications are all closed. */
  async function start() {
    let created: Application | undefined;
    key.current ||= newId();
    const ok = await mutate(async () => {
      try {
        created = await api<Application>("/applications", "POST", {
          job_id: job.id,
          idempotency_key: key.current,
        });
      } catch (error) {
        // Another session started it: open that one.
        if (
          error instanceof ApiError &&
          error.code === "application_in_progress" &&
          typeof error.details?.application_id === "string"
        ) {
          created = { id: error.details.application_id } as Application;
          return;
        }
        throw error;
      }
    }, "Application started.");
    if (ok && created) onOpenApplication(created.id);
  }
  const application = job.application;
  const open = application && application.status !== "closed";
  const fresh = job.triage === "new";
  return (
    <>
      <ActionBar sticky label="Actions on this job">
        {job.triage === "dismissed" ? (
          <Button
            variant="primary"
            disabled={pending}
            onClick={() => triage("new", "Restored.")}
          >
            Restore
          </Button>
        ) : open ? (
          <a className="btn primary" href={reviewHref(application.id)}>
            Open the application
          </a>
        ) : job.triage === "shortlisted" ? (
          <Button variant="primary" disabled={pending} onClick={start}>
            Start a new application
          </Button>
        ) : (
          <Button
            variant="primary"
            disabled={pending}
            onClick={() =>
              triage("shortlisted", "Shortlisted. Its application is started.")
            }
          >
            Shortlist
          </Button>
        )}
        {job.triage === "shortlisted" && (
          <Button
            disabled={pending}
            onClick={() => triage("new", "Back to New.")}
          >
            Back to New
          </Button>
        )}
        {job.triage !== "dismissed" && (
          <Button disabled={pending} onClick={() => setDismissing(true)}>
            Dismiss…
          </Button>
        )}
        {!fresh && (
          <Button variant="quiet" className="only-desktop" onClick={onNote}>
            Add a note
          </Button>
        )}
      </ActionBar>
      {!fresh && (
        <div className="only-mobile">
          <Button variant="quiet" onClick={onNote}>
            Add a note
          </Button>
        </div>
      )}
      {dismissing && (
        <DismissDialog
          what={job.title || "this job"}
          onClose={() => setDismissing(false)}
          onConfirm={async (reason) => {
            if (
              await triage(
                "dismissed",
                "Dismissed. It can be restored from Dismissed.",
                reason,
              )
            )
              setDismissing(false);
          }}
        />
      )}
    </>
  );
}

/** The attempts at this job, newest first, each a link to its review page. */
function Attempts({ job }: { job: Job }) {
  const attempts = useFresh<{ items: Application[]; total: number }>(
    `/applications?job_id=${encodeURIComponent(job.id)}&sort=newest&limit=20`,
    { items: [], total: 0 },
    ["applications"],
  );
  if (!attempts.data.items.length) return null;
  return (
    <section className="detail-section" aria-labelledby="attempts-title">
      <h3 id="attempts-title">Applications</h3>
      <ul className="list compact" aria-label="Applications to this job">
        {attempts.data.items.map((attempt) => (
          <li key={attempt.id}>
            <div className="grow">
              <a className="title" href={reviewHref(attempt.id)}>
                {stageLabels[attempt.status]}
                {attempt.outcome
                  ? ` · ${outcomeLabels[attempt.outcome] || attempt.outcome}`
                  : ""}
              </a>
              <div className="meta">Started {dayTime(attempt.created_at)}</div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Posting({ job }: { job: Job }) {
  const [full, setFull] = useState(false);
  const text = job.posting || "";
  const long = text.length > PREVIEW;
  return (
    <section className="detail-section" aria-labelledby="posting-title">
      <h3 id="posting-title">Posting</h3>
      {text ? (
        <>
          <div className="posting prose">
            {long && !full ? text.slice(0, PREVIEW).trimEnd() + "…" : text}
          </div>
          {long && (
            <Button size="sm" variant="quiet" onClick={() => setFull(!full)}>
              {full ? "Show less" : "Show the full text"}
            </Button>
          )}
        </>
      ) : (
        <p className="muted">
          The posting text is missing. Add it under Details below, or ask your
          agent to complete it.
        </p>
      )}
    </section>
  );
}

/**
 * The selected job: its signals and actions, the duplicate decision, its
 * applications, the posting, its timeline and the details kept with it.
 */
export function Detail({
  id,
  onGone,
  own,
  leaving,
  ...links
}: Links & {
  id: string;
  onGone: () => void;
  own: Set<string> | null;
  /** Before a triage: what shows the next job once this one left the list. */
  leaving: (id: string) => (() => void) | null;
}) {
  const record = useFresh<Job | null>(
    `/jobs/${encodeURIComponent(id)}`,
    null,
    JOB_SCOPES,
  );
  const note = () => {
    const field = document.getElementById("job-note");
    field?.scrollIntoView({ block: "center" });
    field?.focus({ preventScroll: true });
  };
  // On a phone the job replaces the list: move there, as a new screen would.
  const loaded = record.data?.id;
  useEffect(() => {
    if (!loaded || !matchMedia("(max-width: 860px)").matches) return;
    const heading = document.getElementById("job-title");
    heading?.scrollIntoView({ block: "start" });
    heading?.focus({ preventScroll: true });
  }, [loaded]);
  if (record.error)
    return (
      <Card className="detail">
        <div className="body stack">
          <ErrorBanner message={record.error} retry={record.reload} />
          <Button onClick={onGone}>Close</Button>
        </div>
      </Card>
    );
  if (record.loading || !record.data)
    return (
      <Card className="detail">
        <Loading label="Loading the job…" />
      </Card>
    );
  const job = record.data;
  return (
    <section className="card detail job-detail" aria-labelledby="job-title">
      <header className="top">
        <div className="grow">
          <h2 id="job-title" tabIndex={-1}>
            {job.title || "Untitled role"}
          </h2>
          <div className="muted">
            {[job.company, job.location, sourceLabel(job)]
              .filter(Boolean)
              .join(" · ")}
          </div>
        </div>
        {job.url && (
          <a
            className="btn quiet sm"
            href={job.url}
            target="_blank"
            rel="noreferrer"
          >
            Posting <span aria-hidden="true">↗</span>
            <span className="sr"> (the original posting, in a new tab)</span>
          </a>
        )}
      </header>
      <div className="body stack">
        <Signals job={job} own={own} />
        {job.dismissal && (
          <Banner tone="neutral" title={dismissedBy(job)}>
            {[dayTime(job.dismissal.at), job.dismissal.reason]
              .filter(Boolean)
              .join(" · ") || "No reason was given."}
          </Banner>
        )}
        <Actions
          job={job}
          onOpenApplication={links.onOpenApplication}
          onNote={note}
          leaving={leaving}
        />
      </div>
      {job.signals.duplicate && (
        <Duplicate job={job} onOpenJob={links.onOpenJob} />
      )}
      {job.application_count > 0 && <Attempts job={job} />}
      <Posting job={job} />
      <JobTimeline job={job} />
      <JobMore job={job} onGone={onGone} {...links} />
    </section>
  );
}
