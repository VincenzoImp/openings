import { useState } from "react";
import {
  ApiError,
  api,
  downloadWorkspaceFile,
  readinessLabels,
  type Application,
  type ListResult,
  type WorkspaceFile,
} from "../../api";
import { ActionBar, Banner, Button, Dialog, Tag } from "../../design";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";
import { reviewHref } from "../applications/links";
import { planTags, stageOf, stageTag } from "../applications/model";
import { Respond } from "../applications/Respond";
import { nextReady, queuePlace } from "./model";

const NONE = { items: [], total: 0 };
/** The Ready applications in Today's order. */
const READY_QUEUE =
  "/applications?status=draft&ready=true&sort=deadline&limit=200";

/** "1 of 6 ready · Next: Data Platform Engineer", in Today's order. */
function QueuePlace({ id }: { id: string }) {
  const queue = useFresh<ListResult<Application>>(READY_QUEUE, NONE, [
    "applications",
  ]);
  const place = queuePlace(queue.data.items, id);
  if (!place) return null;
  return (
    <span className="caption">
      {place.position} of {place.total} ready
      {place.next && (
        <>
          {" · "}
          <a href={reviewHref(place.next.id)}>
            Next: {place.next.job?.title || "the next application"}
          </a>
        </>
      )}
    </span>
  );
}

/**
 * The application's name, stage and the actions that end the review: mark it
 * applied or stop, download the documents, open the posting; for a sent
 * application, record the employer's answer.
 */
export function Head({
  application,
  pdfs,
  reload,
}: {
  application: Application;
  /** The PDFs of the current CV and letter, to download together. */
  pdfs: WorkspaceFile[];
  reload: () => void;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const [dialog, setDialog] = useState<"stop" | "respond" | null>(null);
  // The last Ready application was just marked applied.
  const [allSent, setAllSent] = useState(false);
  const stage = stageOf(application);
  const tag = stageTag(application);
  const job = application.job;
  const sent = ["applied", "interview", "offer"].includes(application.status);
  const download = () =>
    void Promise.all(pdfs.map((file) => downloadWorkspaceFile(file))).catch(
      (cause) => notify(String(cause), true),
    );
  /**
   * Mark it applied, then go on to the next Ready application in Today's
   * order, with Undo in the toast. After the last one, say so here.
   */
  async function markApplied() {
    const done: {
      next?: Application | null;
      before?: Application;
      after?: Application;
    } = {};
    const ok = await mutate(async () => {
      // Read it again: the Ready mark may have been cleared since the page loaded.
      const fresh = await api<Application>(`/applications/${application.id}`);
      if (fresh.readiness !== "ready")
        throw new ApiError(
          `This application is no longer ready (${(readinessLabels[fresh.readiness || "none"] || "changed").toLowerCase()}), so it was not marked applied. Review it again.`,
          409,
          "application_not_ready",
        );
      const queue = await api<ListResult<Application>>(READY_QUEUE);
      done.next = nextReady(queue.items, application.id);
      done.before = fresh;
      done.after = await api<Application>(
        `/applications/${application.id}`,
        "PATCH",
        { expected_version: fresh.version, status: "applied" },
      );
    }, "Marked applied.");
    const { next, before, after } = done;
    if (!ok || !after || !before) return;
    notify("Marked applied.", false, {
      label: "Undo",
      run: () => void undo(after, before),
    });
    if (next) location.hash = reviewHref(next.id);
    else {
      setAllSent(true);
      reload();
    }
  }
  /** Back to Preparing without a sent day, Ready again as it was. */
  async function undo(sent: Application, previous: Application) {
    const ok = await mutate(async () => {
      const draft = await api<Application>(
        `/applications/${sent.id}`,
        "PATCH",
        {
          expected_version: sent.version,
          status: previous.status,
          applied_at: previous.applied_at ?? null,
        },
      );
      if (previous.ready_at)
        await api(`/applications/${sent.id}/ready`, "POST", {
          expected_version: draft.version,
          ready: true,
        });
    }, "Back to Ready. It was not marked applied.");
    if (!ok) return;
    setAllSent(false);
    if (location.hash === reviewHref(sent.id)) reload();
    else location.hash = reviewHref(sent.id);
  }
  async function stop() {
    if (
      await mutate(
        () =>
          api(`/applications/${application.id}`, "PATCH", {
            expected_version: application.version,
            status: "closed",
            outcome: "not_pursued",
          }),
        "Closed as not pursued.",
      )
    )
      setDialog(null);
  }
  const actions = (mobile: boolean) => (
    <>
      {!!pdfs.length && (
        <Button onClick={download}>
          {mobile
            ? "Download"
            : pdfs.length > 1
              ? "Download CV and letter"
              : "Download the PDF"}
        </Button>
      )}
      {!mobile && job?.url && (
        <a className="btn" href={job.url} target="_blank" rel="noreferrer">
          Open the posting<span aria-hidden="true"> ↗</span>
          <span className="sr"> (opens a new tab)</span>
        </a>
      )}
      {!mobile && application.status === "draft" && (
        <Button variant="quiet" onClick={() => setDialog("stop")}>
          Not pursuing
        </Button>
      )}
      {stage === "ready" && (
        <Button variant="primary" disabled={pending} onClick={markApplied}>
          Mark applied
        </Button>
      )}
      {sent && (
        <Button variant="primary" onClick={() => setDialog("respond")}>
          Record response
        </Button>
      )}
    </>
  );
  return (
    <header className="review-head spread">
      {allSent && (
        <Banner
          tone="info"
          role="status"
          className="all-sent"
          title="All sent."
          action={
            <a className="btn sm" href="#today">
              Back to Today
            </a>
          }
        >
          No other application is ready to apply.
        </Banner>
      )}
      <div className="grow">
        <div className="row">
          <Tag tone={tag.tone}>{tag.text}</Tag>
          {planTags(application).map((item) => (
            <Tag key={item.text} tone={item.tone}>
              {item.text}
            </Tag>
          ))}
          {stage === "ready" && <QueuePlace id={application.id} />}
        </div>
        <h1>{job?.title || "Untitled role"}</h1>
        <p className="muted">
          {[job?.company, job?.location].filter(Boolean).join(" · ")}
        </p>
      </div>
      <div className="only-desktop">
        <ActionBar label="Application actions">{actions(false)}</ActionBar>
      </div>
      {(pdfs.length > 0 || stage === "ready" || sent) && (
        <div className="only-mobile">
          <ActionBar sticky label="Main actions">
            {actions(true)}
          </ActionBar>
        </div>
      )}
      {dialog === "stop" && (
        <Dialog
          title="Stop this application?"
          onClose={() => setDialog(null)}
          footer={
            <>
              <Button onClick={() => setDialog(null)}>Keep preparing</Button>
              <Button variant="danger" disabled={pending} onClick={stop}>
                Close as not pursued
              </Button>
            </>
          }
        >
          <p>
            It closes with the outcome Not pursued. Its documents and history
            stay, Insights does not count it, and you can reopen it later.
          </p>
        </Dialog>
      )}
      {dialog === "respond" && (
        <Dialog
          title="Record the employer's answer"
          onClose={() => setDialog(null)}
        >
          <Respond
            stacked
            application={application}
            reload={reload}
            onDone={() => setDialog(null)}
          />
        </Dialog>
      )}
    </header>
  );
}
