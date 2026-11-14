import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  CalendarDays,
  ChevronLeft,
  ExternalLink,
  MapPin,
  MoreHorizontal,
  SearchX,
  Send,
} from "lucide-react";
import { ApiError } from "../../api/client";
import { TopBarActions, useTitle } from "../../shell/context";
import { href, navigate, useRoute } from "../../shell/router";
import { ToneText } from "../../ui/Badge";
import { Button, IconButton } from "../../ui/Button";
import { Menu, type MenuEntry } from "../../ui/Menu";
import { Icon } from "../../ui/Icon";
import { isTyping } from "../../ui/keys";
import { ActionBar } from "../../ui/Split";
import { LoadError } from "../../ui/LoadError";
import { EmptyState, PageHeader, Skeleton } from "../../ui/Page";
import { useToast } from "../../ui/Toast";
import {
  jobOf,
  useApplication,
  useReadyQueue,
  useSentToday,
  useUpdateApplication,
  type Application,
  type Patch,
} from "../applications/data";
import {
  ApplicationDialogs,
  errorText,
  type DialogKind,
  type Target,
} from "../applications/dialogs";
import { listHref } from "../applications/back";
import {
  deadlinePhrase,
  isSent,
  nextReady,
  reopenStage,
  stageOf,
} from "../applications/model";
import { PriorityGlyph, StatusText, pageHref } from "../applications/Row";
import { FollowUp } from "./FollowUp";
import { Preparing } from "./Preparing";
import { ReadyView } from "./Ready";
import "../applications/applications.css";
import "./application.css";

/** Set before the send loop opens the next application: it slides in. */
let arriving = false;

/** A job title in a toast: “Data Engineer”. */
const quoted = (title: string) => `“${title || "Untitled role"}”`;

/** Back to the list the page was opened from; the h1 below names the job. */
function BackLink() {
  return (
    <a className="apg-back" href={listHref()}>
      <Icon icon={ChevronLeft} size="sm" />
      Applications
    </a>
  );
}

export interface PageContext {
  app: Application;
  noReplyDays: number;
  /** Open one of the application's dialogs. */
  open: (kind: DialogKind) => void;
  /** Change the stage with a toast and its Undo. */
  move: (patch: Patch, message: string, undo?: Patch) => void;
  /** The page's head, with the stage's primary action. */
  header: (actions?: ReactNode) => ReactNode;
}

/** The head of every stage: where it sits, what it is, its menu. */
function Header({
  app,
  noReplyDays,
  menu,
  actions,
}: {
  app: Application;
  noReplyDays: number;
  menu: MenuEntry[];
  actions?: ReactNode;
}) {
  const job = jobOf(app);
  const deadline = deadlinePhrase(app.deadline);
  const more = (tooltip: "below" | "none") => (
    <Menu
      label="Application actions"
      placement="bottom-end"
      items={menu}
      trigger={(props) => (
        <IconButton
          {...props}
          icon={MoreHorizontal}
          label="More actions"
          tooltip={tooltip}
        />
      )}
    />
  );
  const posting = job.url ? (
    <a
      className="ui-btn"
      data-variant="ghost"
      href={job.url}
      target="_blank"
      rel="noreferrer noopener"
    >
      <Icon icon={ExternalLink} />
      <span className="ui-btn-label">Open posting</span>
    </a>
  ) : null;
  return (
    <div className="apg-head">
      <BackLink />
      <PageHeader title={job.title} />
      {/* On a phone the top bar shortens the title; the page shows it whole. */}
      <p className="apg-phone-title" aria-hidden="true">
        {job.title}
      </p>
      <ul className="apg-meta" aria-label="About this application">
        {job.company && <li className="apg-company">{job.company}</li>}
        {job.location && (
          <li>
            <Icon icon={MapPin} size="sm" />
            {job.location}
          </li>
        )}
        <li>
          <StatusText app={app} noReplyDays={noReplyDays} />
        </li>
        {deadline &&
          stageOf(app) !== "shortlisted" &&
          stageOf(app) !== "ready" && (
            <li>
              <Icon icon={CalendarDays} size="sm" />
              <ToneText tone={deadline.tone}>{deadline.text}</ToneText>
            </li>
          )}
        {app.priority != null && (
          <li>
            <PriorityGlyph priority={app.priority} />
            Priority {app.priority}
          </li>
        )}
      </ul>
      <div className="apg-actions">
        {actions}
        {posting}
        {more("below")}
      </div>
      <TopBarActions>
        {job.url && (
          <a
            className="ui-btn ui-icon-btn"
            data-variant="ghost"
            href={job.url}
            target="_blank"
            rel="noreferrer noopener"
            aria-label="Open posting"
          >
            <Icon icon={ExternalLink} />
          </a>
        )}
        {more("none")}
      </TopBarActions>
    </div>
  );
}

/** The `…` entries of an application, by its stage. */
function menuOf(
  app: Application,
  context: Pick<PageContext, "open" | "move">,
  extra: MenuEntry[],
): MenuEntry[] {
  const { open, move } = context;
  const stage = stageOf(app);
  const back = { stage: app.stage } as Patch;
  const staged: MenuEntry[] = [];
  if (isSent(app.stage)) {
    staged.push({
      id: "no-reply",
      label: "Close as no reply",
      onSelect: () =>
        move(
          { stage: "closed", outcome: "no_response" },
          `Closed ${quoted(jobOf(app).title)} as no reply`,
          back,
        ),
    });
    staged.push({
      id: "withdraw",
      label: "Withdraw",
      onSelect: () =>
        move(
          { stage: "closed", outcome: "not_pursued" },
          `Withdrew ${quoted(jobOf(app).title)}`,
          back,
        ),
    });
    if (app.stage === "offer")
      staged.push({
        id: "accept",
        label: "Accept offer",
        onSelect: () =>
          move(
            { stage: "closed", outcome: "accepted" },
            `Accepted the offer for ${quoted(jobOf(app).title)}`,
            back,
          ),
      });
  }
  return [
    ...extra,
    ...staged,
    ...(extra.length || staged.length ? (["separator"] as const) : []),
    { id: "stage", label: "Change stage…", onSelect: () => open("stage") },
    {
      id: "plan",
      label: "Deadline and priority…",
      onSelect: () => open("plan"),
    },
    ...(stage === "shortlisted" || stage === "ready"
      ? [
          {
            id: "required",
            label: "Required documents…",
            onSelect: () => open("required"),
          },
        ]
      : []),
    app.stage === "closed"
      ? {
          id: "reopen",
          label: "Reopen",
          onSelect: () =>
            move(
              { stage: reopenStage(app) },
              `Reopened ${quoted(jobOf(app).title)}`,
              {
                stage: "closed",
                outcome: app.outcome as Patch["outcome"],
              },
            ),
        }
      : { id: "close", label: "Close…", onSelect: () => open("close") },
    "separator",
    {
      id: "delete",
      label: "Delete permanently…",
      danger: true,
      onSelect: () => open("delete"),
    },
  ];
}

function Loading() {
  return (
    <div className="apg" role="status" aria-label="Loading the application">
      <div className="apg-head">
        <BackLink />
        <PageHeader title="Application" />
        <div className="apg-skeleton">
          <Skeleton width={260} height={12} />
        </div>
      </div>
      <div className="apg-panes-skeleton">
        {[0, 1, 2].map((index) => (
          <div className="ap-well ap-well-loading" key={index}>
            <Skeleton width="70%" />
            <Skeleton width="50%" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** "All sent — 5 applications today", after the last one in the queue. */
function AllSent({ sentId }: { sentId: string }) {
  const sent = useSentToday(true).data;
  useTitle("All sent");
  return (
    <div className="apg apg-done">
      <PageHeader title="All sent" />
      <EmptyState
        icon={Send}
        title={`All sent${sent ? ` — ${sent} application${sent === 1 ? "" : "s"} today` : ""}`}
        actions={
          <>
            <a className="ui-btn" data-variant="primary" href={href("today")}>
              <span className="ui-btn-label">Back to Today</span>
            </a>
            <a className="ui-btn" data-variant="ghost" href={pageHref(sentId)}>
              <span className="ui-btn-label">Open the last one</span>
            </a>
          </>
        }
      >
        No other application is ready to send.
      </EmptyState>
    </div>
  );
}

/**
 * One application, on a page whose content follows its stage: Shortlisted
 * shows what is missing and the documents; Ready shows posting, CV and
 * letter side by side with Mark applied and the send loop; sent stages lead
 * with the status, Record reply and the history; Closed with its outcome.
 */
export default function ApplicationPage() {
  const id = useRoute().params.id ?? "";
  const record = useApplication(id);
  const ready = useReadyQueue();
  const update = useUpdateApplication();
  const toast = useToast();
  const [dialog, setDialog] = useState<DialogKind | null>(null);
  const [allSent, setAllSent] = useState<string | null>(null);
  const [arrived] = useState(() => {
    const value = arriving;
    arriving = false;
    return value;
  });
  const app = record.data;
  const job = app ? jobOf(app) : null;
  useTitle(allSent ? "All sent" : (job?.title ?? null));
  const top = useRef<HTMLDivElement>(null);
  const sent = !!app && isSent(app.stage);
  useEffect(() => {
    if (!sent) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "r" || event.metaKey || event.ctrlKey || event.altKey)
        return;
      if (event.defaultPrevented || isTyping(event.target)) return;
      if (document.querySelector("dialog[open], [popover]:popover-open"))
        return;
      event.preventDefault();
      setDialog("reply");
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [sent]);
  useEffect(() => {
    setAllSent(null);
    top.current?.closest(".ui-app-content")?.scrollTo?.({ top: 0 });
  }, [id]);

  if (allSent) return <AllSent sentId={allSent} />;
  if (record.isError && !app)
    return (
      <div className="apg">
        <div className="apg-head">
          <BackLink />
          <PageHeader title="Application" />
        </div>
        {record.error instanceof ApiError && record.error.status === 404 ? (
          <EmptyState
            icon={SearchX}
            title="This application no longer exists"
            actions={
              <a className="ui-btn" data-variant="secondary" href={listHref()}>
                <span className="ui-btn-label">Back to Applications</span>
              </a>
            }
          >
            It may have been deleted.
          </EmptyState>
        ) : (
          <div className="apg-error">
            <LoadError
              what="this application"
              error={record.error}
              retry={() => void record.refetch()}
            />
          </div>
        )}
      </div>
    );
  if (!app || !job) return <Loading />;

  const target: Target = {
    id: app.id,
    version: app.version,
    stage: app.stage,
    title: job.title,
    applied_at: app.applied_at,
    outcome: app.outcome,
    deadline: app.deadline,
    priority: app.priority,
    required_documents: app.required_documents,
  };
  const days = ready.noReplyDays;

  function move(patch: Patch, message: string, undo?: Patch) {
    update.mutate(
      { id: app!.id, version: app!.version, patch },
      {
        onSuccess: (changed) =>
          toast.show({
            message,
            action: undo
              ? {
                  label: "Undo",
                  undo: true,
                  run: () =>
                    update.mutate(
                      { id: changed.id, version: changed.version, patch: undo },
                      {
                        onError: (error) =>
                          toast.show({
                            message: errorText(error),
                            tone: "error",
                          }),
                      },
                    ),
                }
              : undefined,
          }),
        onError: (error) =>
          toast.show({ message: errorText(error), tone: "error" }),
      },
    );
  }

  /**
   * Mark applied, the owner's act: then the next Ready application opens,
   * with Undo; after the last one, "All sent". An error stays here.
   */
  function markApplied(day?: string) {
    const next = nextReady(ready.queue, app!.id);
    const title = job!.title;
    update.mutate(
      {
        id: app!.id,
        version: app!.version,
        patch: {
          stage: "applied",
          ...(day
            ? { applied_at: new Date(`${day}T12:00:00`).toISOString() }
            : {}),
        },
      },
      {
        onSuccess: (changed) => {
          toast.show({
            message: `Marked applied ${quoted(title)}`,
            action: {
              label: "Undo",
              undo: true,
              run: () =>
                update.mutate(
                  {
                    id: changed.id,
                    version: changed.version,
                    patch: { stage: "shortlisted" },
                  },
                  {
                    onSuccess: () => {
                      setAllSent(null);
                      navigate(pageHref(changed.id));
                    },
                    onError: (error) =>
                      toast.show({ message: errorText(error), tone: "error" }),
                  },
                ),
            },
          });
          if (stageOf(app!) !== "ready") return;
          if (next) {
            arriving = true;
            navigate(pageHref(next.id));
          } else setAllSent(changed.id);
        },
        onError: (error) =>
          toast.show({
            message: `Not marked applied: ${errorText(error)}`,
            tone: "error",
          }),
      },
    );
  }

  const stage = stageOf(app);
  const extra: MenuEntry[] =
    stage === "shortlisted"
      ? [
          {
            id: "applied",
            label: "Mark applied",
            onSelect: () => markApplied(),
          },
        ]
      : stage === "ready"
        ? [
            {
              id: "not-pursuing",
              label: "Not pursuing",
              onSelect: () =>
                move(
                  { stage: "closed", outcome: "not_pursued" },
                  `Closed ${quoted(job.title)} · not pursuing`,
                  { stage: "shortlisted" },
                ),
            },
          ]
        : [];
  const menu = menuOf(app, { open: setDialog, move }, extra);
  const context: PageContext = {
    app,
    noReplyDays: days,
    open: setDialog,
    move,
    header: (actions) => (
      <Header app={app} noReplyDays={days} menu={menu} actions={actions} />
    ),
  };

  let body: ReactNode;
  if (stage === "ready")
    body = (
      <ReadyView
        context={context}
        queue={ready.queue}
        busy={update.isPending}
        onMarkApplied={markApplied}
      />
    );
  else if (stage === "shortlisted") body = <Preparing context={context} />;
  else body = <FollowUp context={context} />;

  return (
    <div
      ref={top}
      className="apg"
      data-stage={stage}
      data-arrived={arrived || undefined}
      key={app.id}
    >
      {body}
      {isSent(app.stage) && (
        <ActionBar>
          <Button variant="primary" onClick={() => setDialog("reply")}>
            Record reply
          </Button>
        </ActionBar>
      )}
      <ApplicationDialogs
        open={dialog}
        target={target}
        onClose={() => setDialog(null)}
        onDeleted={() => navigate(listHref())}
      />
    </div>
  );
}
