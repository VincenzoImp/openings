import { Suspense, lazy, useId, useState, type ReactNode } from "react";
import {
  ArrowRight,
  CircleSlash,
  MessageSquareReply,
  Send,
} from "lucide-react";
import type { Schema } from "../../api/client";
import { href, navigate } from "../../shell/router";
import { Count, Dot, ToneText } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { formatDate, formatNumber } from "../../ui/format";
import { STAGES, StatusGlyph, type Stage } from "../../ui/Icon";
import { List, ListRow, ListRows } from "../../ui/List";
import { useToast } from "../../ui/Toast";
import {
  useBulkApplications,
  useRequirementTexts,
  type Application,
} from "./data";
import { deadlineLabel } from "../applications/days";
import { HighPriority } from "../applications/priority";
import { daysSince, missingText, roleOf, type Row } from "./model";

// The reply form loads when it is first opened; Today itself stays small.
const RecordReply = lazy(() =>
  import("./RecordReply").then((module) => ({ default: module.RecordReply })),
);

export type StageCounts = Partial<Record<Stage, number>>;

const SHOWN = 5;
const applicationHref = (id: string) => href("application", { id });
const stageHref = (stage: Stage) => href("applications", {}, { stage: stage });

/** A section of Today: a heading with its count, one action, its rows. */
function Section({
  title,
  count,
  action,
  children,
}: {
  title: string;
  count?: number;
  action?: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section className="today-section" aria-labelledby={id}>
      <header className="today-section-head">
        <h2 id={id}>
          {title}
          {count != null && <Count value={count} />}
        </h2>
        {action && <div className="today-section-action">{action}</div>}
      </header>
      {children}
    </section>
  );
}

/** One list per section, with the List keyboard model (j/k, Enter). */
function Rows({
  label,
  ids,
  shortcuts,
  children,
}: {
  label: string;
  ids: string[];
  shortcuts?: Record<string, (id: string) => void>;
  children: ReactNode;
}) {
  const [active, setActive] = useState<string | null>(null);
  const current = active && ids.includes(active) ? active : (ids[0] ?? null);
  return (
    <List
      label={label}
      className="today-list"
      activeId={current}
      onActiveChange={setActive}
      onOpen={(id) => navigate(applicationHref(id))}
      shortcuts={shortcuts}
    >
      <ListRows>{children}</ListRows>
    </List>
  );
}

/** Ready to apply: the send queue, closest deadline first. */
export function Ready({
  page,
}: {
  page: { items: Application[]; total: number };
}) {
  const first = page.items[0];
  return (
    <Section
      title="Ready to apply"
      count={page.total}
      action={
        first && (
          <Button
            variant="primary"
            icon={Send}
            className="today-start"
            onClick={() => navigate(applicationHref(first.id))}
          >
            Start applying
          </Button>
        )
      }
    >
      <Rows label="Ready applications" ids={page.items.map((row) => row.id)}>
        {page.items.map((row) => {
          const { title, company } = roleOf(row);
          const deadline = deadlineLabel(row.deadline);
          return (
            <ListRow
              key={row.id}
              id={row.id}
              href={applicationHref(row.id)}
              leading={<HighPriority priority={row.priority} />}
              title={title}
              sub={company}
              meta={
                deadline && (
                  <ToneText tone={deadline.tone}>{deadline.text}</ToneText>
                )
              }
            />
          );
        })}
      </Rows>
      {page.total > page.items.length && (
        <a className="today-more" href={stageHref("ready")}>
          All {page.total} ready applications
          <ArrowRight aria-hidden="true" size={14} strokeWidth={1.75} />
        </a>
      )}
    </Section>
  );
}

/** Needs attention: each row names the one thing missing. */
export function Attention({ rows }: { rows: Row[] }) {
  // The text of an open requirement needs the application itself.
  const texts = useRequirementTexts(
    rows
      .filter(
        (row) =>
          !row.missing.some((item) => item === "cv" || item === "letter"),
      )
      .slice(0, SHOWN)
      .map((row) => row.id),
  );
  const shown = rows.slice(0, SHOWN);
  return (
    <Section title="Needs attention" count={rows.length}>
      <Rows
        label="Applications that need attention"
        ids={shown.map((row) => row.id)}
      >
        {shown.map((row) => {
          const { title, company } = roleOf(row);
          const deadline = deadlineLabel(row.deadline);
          const missing = missingText(row, texts);
          return (
            <ListRow
              key={row.id}
              id={row.id}
              href={applicationHref(row.id)}
              leading={
                <StatusGlyph stage={row.ready ? "ready" : "shortlisted"} />
              }
              title={title}
              sub={[company, deadline?.text].filter(Boolean).join(" · ")}
              meta={
                row.ready ? (
                  missing
                ) : (
                  <ToneText tone="warning">{missing}</ToneText>
                )
              }
            />
          );
        })}
      </Rows>
      {rows.length > SHOWN && (
        <a className="today-more" href={stageHref("shortlisted")}>
          All {rows.length}
          <ArrowRight aria-hidden="true" size={14} strokeWidth={1.75} />
        </a>
      )}
    </Section>
  );
}

type BatchResult = Schema<"BatchResult">;

/**
 * Waiting for a reply: sent longer ago than the no-reply period. Each row
 * records the reply or closes as no reply (r, c); the header closes them all.
 * Both closes are undone from the toast.
 */
export function Waiting({ rows, days }: { rows: Application[]; days: number }) {
  const bulk = useBulkApplications();
  const toast = useToast();
  const [replying, setReplying] = useState<Application | null>(null);
  // Once opened, the form stays mounted, so it closes with its exit.
  const [opened, setOpened] = useState(false);
  if (replying && !opened) setOpened(true);
  const shown = rows.slice(0, SHOWN);
  const byId = new Map(rows.map((row) => [row.id, row]));

  async function close(items: Application[], message: string) {
    let result: BatchResult;
    try {
      result = await bulk.mutateAsync({
        action: "close",
        outcome: "no_response",
        items: items.map((row) => ({
          id: row.id,
          expected_version: row.version,
        })),
      });
    } catch (error) {
      toast.show({
        message: error instanceof Error ? error.message : "Could not close.",
        tone: "error",
      });
      return;
    }
    const closed = result.items.filter((item) => item.ok && item.id);
    if (result.failed)
      return toast.show({
        message: `${closed.length} closed; ${result.failed} could not be closed.`,
        tone: "error",
      });
    toast.show({
      message,
      action: {
        label: "Undo",
        undo: true,
        run: () =>
          void bulk
            .mutateAsync({
              action: "reopen",
              stage: "applied",
              items: closed.map((item) => ({
                id: String(item.id),
                expected_version: item.version ?? 0,
              })),
            })
            .catch(() =>
              toast.show({ message: "Could not reopen them.", tone: "error" }),
            ),
      },
    });
  }
  const closeOne = (row: Application) =>
    close([row], `Closed “${roleOf(row).title}” as no reply`);
  const closeAll = () =>
    close(
      rows,
      rows.length === 1
        ? `Closed “${roleOf(rows[0]).title}” as no reply`
        : `Closed ${rows.length} applications as no reply`,
    );
  const run = (act: (row: Application) => void) => (id: string) => {
    const row = byId.get(id);
    if (row) act(row);
  };

  return (
    <Section
      title="Waiting for a reply"
      count={rows.length}
      action={
        <Button
          size="sm"
          variant="ghost"
          disabled={bulk.isPending}
          onClick={closeAll}
        >
          {rows.length === 1
            ? "Close as no reply"
            : `Close all ${rows.length} as no reply`}
        </Button>
      }
    >
      <p className="today-note">No reply after {days} days or more.</p>
      <Rows
        label="Applications waiting for a reply"
        ids={shown.map((row) => row.id)}
        shortcuts={{ r: run(setReplying), c: run(closeOne) }}
      >
        {shown.map((row) => {
          const { title, company } = roleOf(row);
          const waited = row.applied_at ? daysSince(row.applied_at) : null;
          const reply = {
            label: "Record reply",
            icon: MessageSquareReply,
            shortcut: "R",
            onClick: () => setReplying(row),
          };
          const noReply = {
            label: "Close as no reply",
            icon: CircleSlash,
            shortcut: "C",
            onClick: () => void closeOne(row),
          };
          return (
            <ListRow
              key={row.id}
              id={row.id}
              href={applicationHref(row.id)}
              title={title}
              sub={[
                company,
                row.applied_at && `Applied ${formatDate(row.applied_at)}`,
              ]
                .filter(Boolean)
                .join(" · ")}
              meta={waited != null && `${formatNumber(waited)} days`}
              actions={[reply, noReply]}
              swipe={{ left: noReply }}
            />
          );
        })}
      </Rows>
      {rows.length > SHOWN && (
        <a
          className="today-more"
          href={href("applications", {}, { stage: "applied" })}
        >
          All {rows.length} waiting
          <ArrowRight aria-hidden="true" size={14} strokeWidth={1.75} />
        </a>
      )}
      {opened && (
        <Suspense fallback={null}>
          <RecordReply
            application={replying}
            onClose={() => setReplying(null)}
          />
        </Suspense>
      )}
    </Section>
  );
}

type JobPage = { items: Schema<"JobSummary">[]; total: number };

/** New jobs: how many, the first three, and the way to triage them. */
export function NewJobs({ jobs, recent }: { jobs: JobPage; recent: number }) {
  // The count is in the heading; the line says only what it does not.
  const line =
    recent > 0 && recent < jobs.total
      ? `${formatNumber(recent)} since yesterday`
      : null;
  return (
    <Section
      title="New jobs"
      count={jobs.total}
      action={
        <Button
          size="sm"
          icon={ArrowRight}
          onClick={() => navigate(href("jobs"))}
        >
          Go through them
        </Button>
      }
    >
      {line && <p className="today-note">{line}</p>}
      <ul
        className="ui-list-rows today-list today-jobs"
        aria-label="Newest jobs"
      >
        {jobs.items.map((job) => (
          <ListRow
            key={job.id}
            id={job.id}
            href={href("jobs", {}, { job: job.id })}
            leading={<Dot label="New" />}
            title={job.title || "Untitled role"}
            sub={[job.company, job.location].filter(Boolean).join(" · ")}
            meta={formatDate(job.created_at)}
          />
        ))}
      </ul>
    </Section>
  );
}

const STRIP: Stage[] = [
  "shortlisted",
  "ready",
  "applied",
  "interview",
  "offer",
];

/** Where every open application stands: a count per stage, each a link. */
export function Stages({ counts }: { counts: StageCounts }) {
  const value = (stage: Stage) =>
    stage === "shortlisted"
      ? (counts.shortlisted ?? 0) - (counts.ready ?? 0)
      : (counts[stage] ?? 0);
  return (
    <nav className="today-stages" aria-label="Applications by stage">
      <h2 className="today-stages-title">Applications</h2>
      <ul>
        {STRIP.map((stage) => (
          <li key={stage}>
            <a href={stageHref(stage)}>
              <StatusGlyph stage={stage} />
              <span className="today-stage-count">
                {formatNumber(value(stage))}
              </span>
              {STAGES[stage]}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
