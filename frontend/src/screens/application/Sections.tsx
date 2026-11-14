// The parts of the application page: requirements, form answers, the pinned
// note, the history and the posting.
import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, Check, Copy, Plus, X } from "lucide-react";
import { ConflictNotice } from "../../query/ConflictNotice";
import { Button, IconButton } from "../../ui/Button";
import { Checkbox, Input, Textarea, Field } from "../../ui/Field";
import { formatDate, formatFull } from "../../ui/format";
import { Icon } from "../../ui/Icon";
import { Skeleton } from "../../ui/Page";
import { ReadEdit } from "../../ui/ReadEdit";
import { Switch } from "../../ui/Field";
import { useToast } from "../../ui/Toast";
import {
  useSaveNote,
  useTimeline,
  useVersionedUpdate,
  type Application,
} from "../applications/data";
import { errorText } from "../applications/dialogs";
import { actorPhrase, historyLine } from "../applications/model";

type Requirement = Application["requirements"][number];

/** A section of the page: an h2 and its content. */
export function Section({
  id,
  title,
  aside,
  children,
}: {
  id: string;
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="ap-section" aria-labelledby={`ap-${id}`}>
      <header className="ap-section-head">
        <h2 className="ap-section-title" id={`ap-${id}`}>
          {title}
        </h2>
        {aside}
      </header>
      {children}
    </section>
  );
}

/** A section folded until opened: the posting, notes and history. */
export function Fold({
  title,
  count,
  children,
  open,
}: {
  title: string;
  count?: number;
  children: ReactNode;
  open?: boolean;
}) {
  return (
    <details className="ap-fold" open={open}>
      <summary>
        <span className="ap-section-title">{title}</span>
        {count != null && <span className="ui-count">{count}</span>}
      </summary>
      <div className="ap-fold-body">{children}</div>
    </details>
  );
}

/** Copy a text, saying so. */
export function useCopy() {
  const toast = useToast();
  return (text: string, what: string) =>
    navigator.clipboard?.writeText(text).then(
      () => toast.show({ message: `Copied ${what}`, tone: "success" }),
      () => toast.show({ message: "Copying is not allowed here", tone: "error" }),
    );
}

/**
 * The employer's requirements: tick done, add, remove. A blocking one keeps
 * the application from Ready while open and reads in the warning tone.
 */
export function Requirements({
  app,
  editable = true,
}: {
  app: Application;
  editable?: boolean;
}) {
  const update = useVersionedUpdate();
  const toast = useToast();
  const [text, setText] = useState("");
  const [blocking, setBlocking] = useState(false);
  const items = app.requirements ?? [];
  const save = (next: Requirement[], done?: () => void) =>
    update.mutate(
      {
        id: app.id,
        version: app.version,
        patch: {
          requirements: next.map((item) => ({
            id: item.id,
            text: item.text,
            kind: item.kind as never,
            note: item.note ?? "",
            blocking: item.blocking,
            resolved: item.resolved,
          })),
        },
      },
      {
        onSuccess: done,
        onError: (error) => {
          if (!update.conflict)
            toast.show({ message: errorText(error), tone: "error" });
        },
      },
    );
  return (
    <div className="ap-requirements">
      {update.conflict && (
        <ConflictNotice
          onReload={() => void update.reload()}
          onKeepEditing={() => void update.keepEditing()}
        />
      )}
      {items.length > 0 && (
        <ul className="ap-reqs" aria-label="Requirements">
          {items.map((item) => (
            <li key={item.id} data-blocking={(item.blocking && !item.resolved) || undefined}>
              {editable ? (
                <Checkbox
                  label={item.text}
                  checked={item.resolved}
                  disabled={update.isPending}
                  hint={
                    item.blocking && !item.resolved
                      ? "Blocking: Ready waits for it"
                      : item.note || undefined
                  }
                  onChange={(event) =>
                    save(
                      items.map((other) =>
                        other.id === item.id
                          ? { ...other, resolved: event.target.checked }
                          : other,
                      ),
                    )
                  }
                />
              ) : (
                <span className="ap-req-read">
                  <Icon icon={item.resolved ? Check : X} size="sm" />
                  <span>
                    {item.text}
                    <span className="ui-sr">
                      {item.resolved ? ", done" : ", open"}
                    </span>
                  </span>
                </span>
              )}
              {item.blocking && !item.resolved && (
                <Icon icon={AlertTriangle} size="sm" className="ap-warn" />
              )}
              {editable && (
                <IconButton
                  icon={X}
                  size="sm"
                  label={`Remove requirement: ${item.text}`}
                  tooltip="none"
                  className="ap-req-remove"
                  disabled={update.isPending}
                  onClick={() =>
                    save(items.filter((other) => other.id !== item.id))
                  }
                />
              )}
            </li>
          ))}
        </ul>
      )}
      {editable && (
        <form
          className="ap-req-add"
          onSubmit={(event) => {
            event.preventDefault();
            if (!text.trim()) return;
            save(
              [
                ...items,
                {
                  text: text.trim(),
                  kind: "other",
                  note: "",
                  blocking,
                  resolved: false,
                } as Requirement,
              ],
              () => {
                setText("");
                setBlocking(false);
              },
            );
          }}
        >
          <Input
            aria-label="New requirement"
            placeholder="Add a requirement"
            value={text}
            maxLength={2000}
            onChange={(event) => setText(event.target.value)}
          />
          <Switch
            label="Blocking"
            checked={blocking}
            onChange={(event) => setBlocking(event.target.checked)}
          />
          <Button
            type="submit"
            size="sm"
            icon={Plus}
            disabled={!text.trim() || update.isPending}
          >
            Add
          </Button>
        </form>
      )}
    </div>
  );
}

type Question = { id: string; label: string; required?: boolean };
const questionsOf = (app: Application) =>
  (app.questions ?? []) as unknown as Question[];
const answerText = (value: unknown) =>
  value === true ? "Yes" : value === false ? "No" : value == null ? "" : String(value);

/** The answers of the application form: question, answer, copy. */
export function Answers({ app }: { app: Application }) {
  const questions = questionsOf(app);
  const copy = useCopy();
  if (!questions.length) return null;
  return (
    <dl className="ap-answers" aria-label="Form answers">
      {questions.map((question) => {
        const answer = answerText(app.answers?.[question.id]);
        return (
          <div key={question.id} className="ap-answer">
            <dt>
              {question.label}
              {question.required && !answer && (
                <span className="ap-warn-text"> · required</span>
              )}
            </dt>
            <dd>
              {answer ? (
                <>
                  <span>{answer}</span>
                  <IconButton
                    icon={Copy}
                    size="sm"
                    label={`Copy the answer to ${question.label}`}
                    tooltip="none"
                    onClick={() => void copy(answer, "the answer")}
                  />
                </>
              ) : (
                <span className="ap-muted">No answer yet</span>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/** The pinned note: read first, Edit on purpose. */
export function PinnedNote({ app }: { app: Application }) {
  const note = app.pinned_note ?? null;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note?.body ?? "");
  const saveNote = useSaveNote();
  const toast = useToast();
  useEffect(() => {
    if (!editing) setDraft(note?.body ?? "");
  }, [editing, note?.body]);
  return (
    <ReadEdit
      title="Notes"
      editing={editing}
      onEdit={() => setEditing(true)}
      read={
        note?.body ? (
          <p className="ap-note">{note.body}</p>
        ) : (
          <p className="ap-muted">
            Nothing yet. Notes for this application stay at the top.
          </p>
        )
      }
      form={
        <>
          {saveNote.conflict && (
            <ConflictNotice
              onReload={() => {
                void saveNote.reload();
                setEditing(false);
              }}
              onKeepEditing={() => void saveNote.keepEditing()}
            />
          )}
          <Field label="Note">
            <Textarea
              rows={5}
              value={draft}
              maxLength={20000}
              onChange={(event) => setDraft(event.target.value)}
            />
          </Field>
        </>
      }
      changes={draft.trim() !== (note?.body ?? "").trim() ? 1 : 0}
      saving={saveNote.isPending}
      onSave={() =>
        saveNote.mutate(
          {
            jobId: app.job_id,
            applicationId: app.id,
            note: note && { id: note.id, version: note.version },
            body: draft.trim(),
          },
          {
            onSuccess: () => {
              setEditing(false);
              toast.show({ message: "Note saved", tone: "success" });
            },
            onError: (error) => {
              if (!saveNote.conflict)
                toast.show({ message: errorText(error), tone: "error" });
            },
          },
        )
      }
      onDiscard={() => setEditing(false)}
    />
  );
}

/**
 * Replies, stage changes and notes, newest first, with who made them. "Show
 * all changes" adds every recorded change (fields, documents, the job's).
 */
export function HistoryList({ app }: { app: Application }) {
  const timeline = useTimeline(app.id);
  const [all, setAll] = useState(false);
  const replies = new Map((app.replies ?? []).map((reply) => [reply.id, reply]));
  const items = (timeline.data?.items ?? [])
    .filter((item) => item.id !== app.pinned_note?.id)
    .map((item) => {
      const event = item.event as {
        kind?: string;
        payload?: Record<string, unknown>;
        subject?: { id?: string };
      } | null;
      const reply = event?.subject?.id ? replies.get(event.subject.id) : null;
      return {
        item,
        line: historyLine(
          {
            type: item.type,
            kind: item.kind,
            event,
            note: item.note as { body?: unknown } | null,
          },
          reply,
        ),
      };
    })
    .filter(({ item, line }) => all || (line.main && item.application_id));
  return (
    <div className="ap-history">
      {!timeline.data ? (
        <Skeleton width="70%" />
      ) : (
        <ol className="ap-events" aria-label="History">
          {items.map(({ item, line }) => (
            <li key={item.id} data-type={item.type}>
              <span className="ap-event-dot" aria-hidden="true" />
              <div className="ap-event-text">
                <p>{line.text}</p>
                {line.detail && <p className="ap-event-detail">{line.detail}</p>}
                <p className="ap-event-meta">
                  <time dateTime={item.created_at} title={formatFull(item.created_at)}>
                    {formatDate(item.created_at)}
                  </time>
                  {actorPhrase(item.actor) && ` · ${actorPhrase(item.actor)}`}
                </p>
              </div>
            </li>
          ))}
          {!items.length && <li className="ap-muted">Nothing recorded yet.</li>}
        </ol>
      )}
      <Switch
        label="Show all changes"
        checked={all}
        onChange={(event) => setAll(event.target.checked)}
      />
    </div>
  );
}

/** The posting text, in paragraphs. */
export function PostingText({ text }: { text: string }) {
  if (!text.trim())
    return <p className="ap-muted">No posting text was saved for this job.</p>;
  return (
    <div className="ui-prose ap-posting">
      {text
        .split(/\n+/)
        .map((block) => block.trim())
        .filter(Boolean)
        .map((block, index) =>
          block.length < 48 && !/[.:;,!?]$/.test(block) ? (
            <h3 key={index}>{block}</h3>
          ) : (
            <p key={index}>{block}</p>
          ),
        )}
    </div>
  );
}
