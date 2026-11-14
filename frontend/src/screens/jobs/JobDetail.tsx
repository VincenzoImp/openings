import { useState, type FormEvent } from "react";
import {
  Bookmark,
  Building2,
  ChevronRight,
  Clock,
  Ellipsis,
  ExternalLink,
  Globe,
  Layers,
  MapPin,
  RotateCcw,
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";
import { Status, Tags, ToneText } from "../../ui/Badge";
import { Button, IconButton } from "../../ui/Button";
import { Checkbox, Field, Textarea } from "../../ui/Field";
import { formatDate, formatDay, formatFull } from "../../ui/format";
import { Icon, STAGES, type Stage } from "../../ui/Icon";
import { Menu, type MenuEntry } from "../../ui/Menu";
import {
  Callout,
  MetaLine,
  Properties,
  Prose,
  Skeleton,
  SkeletonRows,
} from "../../ui/Page";
import { ActionBar, DetailBar, DetailBody } from "../../ui/Split";
import { useToast } from "../../ui/Toast";
import { href } from "../../shell/router";
import { useAddNote, useDuplicate, useJob, useTimeline } from "./data";
import {
  actorPhrase,
  closesSoon,
  deadlineOf,
  eventTitle,
  jobTypeText,
  languageLine,
  postingBlocks,
  reasonsLine,
  salaryText,
  signalTags,
  sourceLabel,
  workStyle,
  type Job,
  type JobSummary,
} from "./model";

/** What the detail can ask the screen to do with its job. */
export interface DetailHandlers {
  shortlist: (job: JobSummary) => void;
  dismiss: (job: JobSummary) => void;
  restore: (job: JobSummary) => void;
  correct: (job: Job) => void;
  merge: (job: Job) => void;
  sources: (job: Job) => void;
  forget: (job: JobSummary) => void;
  mergeInto: (job: Job, other: Job) => void;
  keepBoth: (job: Job, other: Job) => void;
  select: (id: string) => void;
}

const lower = (text: string) => text.charAt(0).toLowerCase() + text.slice(1);
/** "Found 3h ago", "Found yesterday", "Found 13 Nov". */
function found(value: string) {
  const when = formatDate(value);
  return /^\d+[mhd]$/.test(when) ? `Found ${when} ago` : `Found ${lower(when)}`;
}

const stageOf = (job: JobSummary): Stage | null => {
  const status = job.application?.status;
  return status && status in STAGES ? (status as Stage) : null;
};

/**
 * The decision of the job's state: Shortlist (the one primary) and Dismiss
 * for a new job, Restore for a dismissed one, the application otherwise.
 */
function Decision({
  job,
  on,
  touch = false,
}: {
  job: JobSummary;
  on: DetailHandlers;
  touch?: boolean;
}) {
  const size = touch ? "touch" : "md";
  if (job.triage === "new")
    return (
      <>
        {touch ? (
          <Button size={size} icon={X} onClick={() => on.dismiss(job)}>
            Dismiss
          </Button>
        ) : null}
        <Button
          variant="primary"
          size={size}
          icon={Bookmark}
          kbd={touch ? undefined : "S"}
          onClick={() => on.shortlist(job)}
        >
          Shortlist
        </Button>
        {touch ? null : (
          <Button variant="ghost" kbd="D" onClick={() => on.dismiss(job)}>
            Dismiss
          </Button>
        )}
      </>
    );
  if (job.triage === "dismissed")
    return (
      <Button
        variant="primary"
        size={size}
        icon={RotateCcw}
        kbd={touch ? undefined : "R"}
        onClick={() => on.restore(job)}
      >
        Restore
      </Button>
    );
  if (job.application)
    return (
      <a
        className="ui-btn"
        data-variant="primary"
        data-size={touch ? "touch" : undefined}
        href={href("application", { id: job.application.id })}
      >
        <span className="ui-btn-label">Open application</span>
      </a>
    );
  return null;
}

/** The one callout of a job: a possible duplicate, or incomplete text. */
function JobCallout({ job, on }: { job: Job; on: DetailHandlers }) {
  const otherId =
    typeof job.signals.duplicate?.job_id === "string"
      ? job.signals.duplicate.job_id
      : null;
  const { other, reasons } = useDuplicate(job.id, otherId);
  if (otherId && other)
    return (
      <Callout
        icon={Layers}
        title={
          <>
            Possibly the same job as{" "}
            <a
              href={href("jobs", {}, { section: "all", job: other.id })}
              onClick={(event) => {
                if (event.button || event.metaKey || event.ctrlKey) return;
                event.preventDefault();
                on.select(other.id);
              }}
            >
              {other.title || "Untitled role"}
            </a>
          </>
        }
        actions={
          <>
            <Button size="sm" onClick={() => on.mergeInto(job, other)}>
              Merge into one job
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => on.keepBoth(job, other)}
            >
              Keep both
            </Button>
          </>
        }
      >
        {[other.company, sourceLabel(other), formatDay(other.created_at)]
          .filter(Boolean)
          .join(" · ")}
        .{reasonsLine(reasons) ? ` ${reasonsLine(reasons)}` : ""}
      </Callout>
    );
  if (job.complete === false)
    return (
      <Callout
        icon={TriangleAlert}
        tone="warning"
        title="The posting text is incomplete"
        actions={
          <Button size="sm" onClick={() => on.correct(job)}>
            Correct details
          </Button>
        }
      >
        The source gave only part of it. Open the posting to read the rest, or
        paste the full text.
      </Callout>
    );
  return null;
}

/** The posting with its headings, paragraphs and lists, at most 66ch. */
function Posting({ job, loading }: { job: Job; loading: boolean }) {
  if (loading && !job.posting)
    return (
      <div className="jobs-posting-loading" aria-hidden="true">
        {[92, 88, 95, 60, 90, 84].map((width, index) => (
          <Skeleton key={index} width={`${width}%`} height={12} />
        ))}
      </div>
    );
  if (!job.posting.trim())
    return <p className="jobs-muted">This job has no posting text yet.</p>;
  return (
    <Prose>
      {postingBlocks(job.posting).map((block, index) =>
        block.kind === "heading" ? (
          <h3 key={index}>{block.text}</h3>
        ) : block.kind === "list" ? (
          <ul key={index}>
            {block.items.map((item, at) => (
              <li key={at}>{item}</li>
            ))}
          </ul>
        ) : (
          <p key={index}>{block.text}</p>
        ),
      )}
    </Prose>
  );
}

/** Notes and the recorded history, collapsed until opened. */
function History({ job }: { job: Job }) {
  const [open, setOpen] = useState(false);
  const timeline = useTimeline(job.id, open);
  const add = useAddNote(job.id);
  const toast = useToast();
  const [body, setBody] = useState("");
  const [pinned, setPinned] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!body.trim()) return;
    try {
      await add.mutateAsync({ body: body.trim(), pinned });
      setBody("");
      setPinned(false);
    } catch (error) {
      toast.show({
        tone: "error",
        message: `The note was not saved: ${(error as Error).message}`,
      });
    }
  }
  const items = timeline.data?.items ?? [];
  return (
    <details
      className="jobs-history"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <Icon icon={ChevronRight} size="sm" className="jobs-history-chevron" />
        Notes and history
      </summary>
      <form className="jobs-note" onSubmit={submit}>
        <Field label="Add a note">
          <Textarea
            rows={2}
            value={body}
            onChange={(event) => setBody(event.target.value)}
          />
        </Field>
        <div className="jobs-note-actions">
          <Checkbox
            label="Pin it to the top"
            checked={pinned}
            onChange={(event) => setPinned(event.target.checked)}
          />
          {body.trim() && (
            <Button size="sm" type="submit" disabled={add.isPending}>
              Add note
            </Button>
          )}
        </div>
      </form>
      {open && timeline.isPending ? (
        <SkeletonRows rows={2} />
      ) : (
        <ol className="jobs-timeline" aria-label="History of this job">
          {items.map((item) => {
            const note = item.note as
              { body?: string; pinned?: boolean } | null | undefined;
            const by = actorPhrase(item.actor);
            const when = (
              <time
                dateTime={item.created_at}
                title={formatFull(item.created_at)}
              >
                {formatDate(item.created_at)}
              </time>
            );
            return (
              <li key={item.id} data-kind={item.type}>
                {note ? (
                  <>
                    <p className="jobs-timeline-note">{note.body}</p>
                    <p className="jobs-timeline-meta">
                      {note.pinned ? "Pinned note" : "Note"}
                      {by ? ` ${by}` : ""} · {when}
                    </p>
                  </>
                ) : (
                  <p className="jobs-timeline-meta">
                    <span className="jobs-timeline-event">
                      {eventTitle(item.event ?? {})}
                    </span>
                    {by ? ` ${by}` : ""} · {when}
                    {typeof item.event?.payload === "object" &&
                    (item.event.payload as { reason?: unknown })?.reason ? (
                      <span className="jobs-timeline-reason">
                        {String(
                          (item.event.payload as { reason: unknown }).reason,
                        )}
                      </span>
                    ) : null}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </details>
  );
}

/**
 * The selected job: a sticky bar (previous/next, "2 of 11", the posting and
 * the … menu), its title and meta, the decision, at most one callout, its
 * properties, the posting and its notes and history. On a phone the
 * decision sits in a sticky bar at the bottom.
 */
export function JobDetail({
  id,
  row,
  position,
  total,
  onPrevious,
  onNext,
  onBack,
  on,
  pushed = false,
}: {
  id: string;
  row?: JobSummary;
  position?: number;
  total?: number;
  onPrevious: () => void;
  onNext: () => void;
  onBack: () => void;
  on: DetailHandlers;
  /** Shown as its own page (a phone): the title is the page's heading. */
  pushed?: boolean;
}) {
  const query = useJob(id, row);
  const job = query.data;
  const Heading = pushed ? "h1" : "h2";
  if (!job)
    return (
      <>
        <DetailBar onBack={onBack} />
        <DetailBody>
          {query.isError ? (
            <Callout
              icon={TriangleAlert}
              tone="danger"
              title="This job could not be loaded"
              actions={
                <Button size="sm" onClick={() => void query.refetch()}>
                  Try again
                </Button>
              }
            >
              {(query.error as Error).message}
            </Callout>
          ) : (
            <div
              className="jobs-detail-loading"
              role="status"
              aria-label="Loading the job"
            >
              <Skeleton width="60%" height={22} />
              <Skeleton width="45%" height={12} />
              <Skeleton width="30%" height={32} />
            </div>
          )}
        </DetailBody>
      </>
    );
  const loading = query.isPlaceholderData;
  const deadline = deadlineOf(job.metadata);
  const stage = stageOf(job);
  const callout = job.signals.duplicate
    ? "duplicate"
    : job.complete === false
      ? "incomplete"
      : null;
  const tags = signalTags(job).filter(
    (tag) =>
      !(callout === "duplicate" && tag === "Possible duplicate") &&
      !(callout === "incomplete" && tag === "Text incomplete") &&
      !tag.startsWith("Requires"),
  );
  const menu: MenuEntry[] = [
    ...(job.triage === "new"
      ? [
          {
            id: "shortlist",
            label: "Shortlist",
            icon: Bookmark,
            kbd: "S",
            onSelect: () => on.shortlist(job),
          },
          {
            id: "dismiss",
            label: "Dismiss",
            icon: X,
            kbd: "D",
            onSelect: () => on.dismiss(job),
          },
          "separator" as const,
        ]
      : job.triage === "dismissed"
        ? [
            {
              id: "restore",
              label: "Restore",
              icon: RotateCcw,
              kbd: "R",
              onSelect: () => on.restore(job),
            },
            "separator" as const,
          ]
        : []),
    {
      id: "correct",
      label: "Correct details",
      kbd: "E",
      disabled: loading,
      onSelect: () => on.correct(job),
    },
    {
      id: "merge",
      label: "Merge with another job…",
      disabled: loading,
      onSelect: () => on.merge(job),
    },
    {
      id: "sources",
      label: "Sources of this job",
      icon: Globe,
      disabled: loading,
      onSelect: () => on.sources(job),
    },
    "separator",
    {
      id: "forget",
      label: "Forget permanently…",
      icon: Trash2,
      danger: true,
      onSelect: () => on.forget(job),
    },
  ];
  return (
    <>
      <DetailBar
        position={position}
        total={total}
        onPrevious={position ? onPrevious : undefined}
        onNext={position ? onNext : undefined}
        onBack={onBack}
      >
        {job.url && (
          <a
            className="ui-btn jobs-posting-link"
            data-variant="ghost"
            data-size="sm"
            href={job.url}
            target="_blank"
            rel="noreferrer"
            aria-keyshortcuts="O"
          >
            <Icon icon={ExternalLink} />
            <span className="ui-btn-label">Open posting</span>
          </a>
        )}
        <Menu
          label="Job actions"
          items={menu}
          placement="bottom-end"
          trigger={(props) => (
            <IconButton
              {...props}
              icon={Ellipsis}
              label="More actions"
              size="sm"
            />
          )}
        />
      </DetailBar>
      <DetailBody className="jobs-detail">
        <Heading id="job-title" className="jobs-title" tabIndex={-1}>
          {job.title || "Untitled role"}
        </Heading>
        <MetaLine
          items={[
            ...(job.company
              ? [{ icon: Building2, text: job.company, label: "Company" }]
              : []),
            ...(job.location
              ? [{ icon: MapPin, text: job.location, label: "Place" }]
              : []),
            { icon: Globe, text: sourceLabel(job), label: "Source" },
            {
              icon: Clock,
              text: (
                <time
                  dateTime={job.created_at}
                  title={formatFull(job.created_at)}
                >
                  {found(job.created_at)}
                </time>
              ),
              label: "Found",
            },
          ]}
        />
        {job.triage === "dismissed" && job.dismissal && (
          <p className="jobs-dismissal">
            Dismissed {actorPhrase(job.dismissal.by)}
            {job.dismissal.at
              ? ` · ${lower(formatDate(job.dismissal.at))}`
              : ""}
            {job.dismissal.reason ? (
              <span className="jobs-dismissal-reason">
                {" "}
                · {job.dismissal.reason}
              </span>
            ) : null}
          </p>
        )}
        <div className="jobs-decision">
          <Decision job={job} on={on} />
          {stage && <Status stage={stage} />}
        </div>
        {callout && (
          <div className="jobs-callout">
            <JobCallout job={job} on={on} />
          </div>
        )}
        <div className="jobs-props">
          <Properties
            items={[
              { label: "Language", value: languageLine(job) },
              { label: "Salary", value: salaryText(job.metadata) },
              {
                label: "Deadline",
                value: deadline ? (
                  <ToneText tone={closesSoon(deadline) ? "warning" : undefined}>
                    {formatDay(deadline)}
                  </ToneText>
                ) : null,
              },
              { label: "Work style", value: workStyle(job.metadata) },
              { label: "Job type", value: jobTypeText(job.job_type) },
              {
                label: "Signals",
                value: tags.length ? <Tags items={tags} /> : null,
              },
            ]}
          />
        </div>
        <section className="jobs-posting" aria-label="Posting">
          <Posting job={job} loading={loading} />
        </section>
        {!loading && <History job={job} />}
      </DetailBody>
      <ActionBar>
        <Decision job={job} on={on} touch />
      </ActionBar>
    </>
  );
}
