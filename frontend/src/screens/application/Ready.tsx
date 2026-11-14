import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
} from "lucide-react";
import { navigate } from "../../shell/router";
import { Button, IconButton } from "../../ui/Button";
import { Field, Input } from "../../ui/Field";
import { Icon } from "../../ui/Icon";
import { isTyping } from "../../ui/keys";
import { Popover } from "../../ui/Menu";
import { Skeleton } from "../../ui/Page";
import { ActionBar } from "../../ui/Split";
import { Tabs } from "../../ui/Tabs";
import { useToast } from "../../ui/Toast";
import { jobOf, type ApplicationRow } from "../applications/data";
import { errorText } from "../applications/dialogs";
import { isoDay, queuePlace, shortDay } from "../applications/model";
import { pageHref } from "../applications/Row";
import {
  KIND_LABEL,
  RevisionView,
  downloadFile,
  pdfOf,
  useCurrentDocuments,
  type Kind,
} from "./Documents";
import type { PageContext } from "./Page";
import { Answers, PostingText, Requirements } from "./Sections";

type Pane = "check" | "posting" | Kind;
/**
 * How the review shows: three panes side by side from 1200 px, one pane at
 * a time behind tabs below that (the check above them), and on a phone the
 * check is a tab too.
 */
type Layout = "side" | "tabs" | "phone";
const layoutOf = (width: number): Layout =>
  width < 720 ? "phone" : width < 1200 ? "tabs" : "side";

/** The layout for the width of the page, followed as it changes. */
function useLayout() {
  const ref = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<Layout>("side");
  useLayoutEffect(() => {
    const page = ref.current?.parentElement;
    if (!page) return;
    const measure = () => setLayout(layoutOf(page.clientWidth));
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(page);
    return () => observer.disconnect();
  }, []);
  return { ref, layout };
}

/** "2 of 5 ready · Next: Data Engineer · Orbit →", with [ and ]. */
function QueuePlace({ queue, id }: { queue: ApplicationRow[]; id: string }) {
  const place = queuePlace(queue, id);
  if (!place) return null;
  const name = (app: ApplicationRow) => {
    const job = jobOf(app);
    return [job.title, job.company].filter(Boolean).join(" · ");
  };
  return (
    <nav className="apg-queue" aria-label="Ready queue">
      <IconButton
        icon={ChevronLeft}
        size="sm"
        label="Previous ready application"
        shortcut="["
        disabled={!place.previous}
        onClick={() => place.previous && navigate(pageHref(place.previous.id))}
      />
      <IconButton
        icon={ChevronRight}
        size="sm"
        label="Next ready application"
        shortcut="]"
        disabled={!place.next}
        onClick={() => place.next && navigate(pageHref(place.next.id))}
      />
      <span className="apg-queue-pos">
        {place.position} of {place.total} ready
      </span>
      {place.next && (
        <a className="apg-queue-next" href={pageHref(place.next.id)}>
          <span className="apg-queue-label">Next: </span>
          <span className="apg-queue-name">{name(place.next)}</span>
          <Icon icon={ChevronRight} size="sm" />
        </a>
      )}
    </nav>
  );
}

/** Mark applied, with the day it was sent (today unless changed). */
function MarkApplied({
  busy,
  day,
  onDay,
  onMark,
}: {
  busy: boolean;
  day: string;
  onDay: (day: string) => void;
  onMark: () => void;
}) {
  const today = isoDay();
  return (
    <span className="apg-mark">
      <Button
        variant="primary"
        kbd="⇧↵"
        aria-keyshortcuts="Shift+Enter"
        disabled={busy}
        onClick={onMark}
      >
        {busy ? "Marking…" : "Mark applied"}
      </Button>
      <Popover
        label="Day it was sent"
        placement="bottom-end"
        trigger={(props) => (
          <IconButton
            {...props}
            icon={CalendarDays}
            label={
              day === today
                ? "Sent today: change the day"
                : `Sent ${shortDay(day)}: change the day`
            }
          />
        )}
      >
        <Field label="Sent on" hint="Today unless you sent it earlier.">
          <Input
            type="date"
            value={day}
            max={today}
            onChange={(event) => onDay(event.target.value || today)}
          />
        </Field>
      </Popover>
      {day !== today && (
        <span className="apg-mark-day">Sent {shortDay(day)}</span>
      )}
    </span>
  );
}

/**
 * Ready: the last check, then send and go on. Before you send (open
 * requirements, the form's answers, the employer's site, both PDFs), then
 * posting, CV and letter side by side. Mark applied (⇧↵) opens the next
 * Ready application; [ and ] move in the queue.
 */
export function ReadyView({
  context,
  queue,
  busy,
  onMarkApplied,
}: {
  context: PageContext;
  queue: ApplicationRow[];
  busy: boolean;
  onMarkApplied: (day?: string) => void;
}) {
  const { app } = context;
  const job = jobOf(app);
  const current = useCurrentDocuments(app.id);
  const toast = useToast();
  const [day, setDay] = useState(isoDay());
  const [chosen, setPane] = useState<Pane>("check");
  const { ref, layout } = useLayout();
  // Beside the panes or above the tabs the check is always shown; a pane is.
  const pane: Pane =
    layout !== "phone" && chosen === "check" ? "posting" : chosen;
  const mark = () => onMarkApplied(day === isoDay() ? undefined : day);
  const kinds = (["cv", "letter"] as Kind[]).filter(
    (kind) => current[kind] || (app.required_documents ?? []).includes(kind),
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (
        event.defaultPrevented ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey
      )
        return;
      if (document.querySelector("dialog[open], [popover]:popover-open"))
        return;
      if (event.key === "Enter" && event.shiftKey) {
        if (isTyping(event.target)) return;
        event.preventDefault();
        if (!busy) mark();
        return;
      }
      if (isTyping(event.target)) return;
      if (event.key !== "]" && event.key !== "[") return;
      const place = queuePlace(queue, app.id);
      const to = event.key === "]" ? place?.next : place?.previous;
      if (!to) return;
      event.preventDefault();
      navigate(pageHref(to.id));
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const downloadBoth = async () => {
    try {
      for (const kind of kinds) {
        const pdf = pdfOf(current[kind]);
        if (pdf)
          await downloadFile(
            pdf,
            `${KIND_LABEL[kind]} - ${[job.company, job.title].filter(Boolean).join(" - ")}.pdf`,
          );
      }
    } catch (error) {
      toast.show({ message: errorText(error), tone: "error" });
    }
  };

  const open = (app.requirements ?? []).filter((item) => !item.resolved);
  const check = (
    <section className="apg-check" aria-labelledby="apg-check-title">
      <h2 className="ap-section-title" id="apg-check-title">
        Before you send
      </h2>
      <div className="apg-check-links">
        {job.url && (
          <a
            className="ui-btn"
            data-variant="secondary"
            href={job.url}
            target="_blank"
            rel="noreferrer noopener"
          >
            <Icon icon={ExternalLink} />
            <span className="ui-btn-label">Apply on employer's site</span>
          </a>
        )}
        <Button icon={Download} onClick={() => void downloadBoth()}>
          Download {kinds.map((kind) => KIND_LABEL[kind]).join(" + ")}
        </Button>
      </div>
      {open.length > 0 && (
        <div className="apg-check-part">
          <h3 className="ap-sub-title">Open requirements</h3>
          <Requirements app={app} />
        </div>
      )}
      {(app.questions ?? []).length > 0 && (
        <div className="apg-check-part">
          <h3 className="ap-sub-title">Form answers</h3>
          <Answers app={app} />
        </div>
      )}
    </section>
  );
  const panes: { id: Pane; label: string }[] = [
    ...(layout === "phone" ? [{ id: "check" as Pane, label: "Check" }] : []),
    { id: "posting", label: "Posting" },
    ...kinds.map((kind) => ({ id: kind, label: KIND_LABEL[kind] })),
  ];
  const docPane = (kind: Kind) => {
    const revision = current[kind];
    return (
      <section
        className="apg-pane"
        data-pane={kind}
        aria-label={KIND_LABEL[kind]}
        key={kind}
      >
        <h2 className="apg-pane-title">{KIND_LABEL[kind]}</h2>
        {revision ? (
          <RevisionView revision={revision} kind={kind} />
        ) : (
          <div className="ap-well ap-well-loading">
            {current.loading ? (
              <>
                <Skeleton width="60%" />
                <Skeleton width="40%" />
              </>
            ) : (
              <p className="ap-pdf-missing">No {KIND_LABEL[kind]} uploaded.</p>
            )}
          </div>
        )}
      </section>
    );
  };
  return (
    <>
      {context.header(
        <MarkApplied busy={busy} day={day} onDay={setDay} onMark={mark} />,
      )}
      <QueuePlace queue={queue} id={app.id} />
      {layout === "tabs" && <div className="apg-ready-check">{check}</div>}
      {layout !== "side" && (
        <Tabs
          className="apg-tabs"
          label="Shown part"
          idPrefix="apg"
          value={pane}
          onChange={(id) => setPane(id as Pane)}
          items={panes}
        />
      )}
      <div
        ref={ref}
        className="apg-ready"
        id="apg-panel"
        data-pane={pane}
        data-layout={layout}
        role="group"
        aria-label="Application to send"
      >
        {layout !== "tabs" && <div className="apg-ready-check">{check}</div>}
        <div className="apg-panes" data-count={kinds.length + 1}>
          <section
            className="apg-pane"
            data-pane="posting"
            aria-label="Posting"
          >
            <h2 className="apg-pane-title">Posting</h2>
            <div
              className="apg-pane-scroll"
              tabIndex={0}
              role="group"
              aria-label="Posting text"
            >
              <PostingText text={job.posting} />
            </div>
          </section>
          {kinds.map(docPane)}
        </div>
      </div>
      <ActionBar>
        <Button variant="primary" disabled={busy} onClick={mark}>
          {busy ? "Marking…" : "Mark applied"}
        </Button>
      </ActionBar>
    </>
  );
}
