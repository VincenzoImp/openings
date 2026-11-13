// What Activity and Today share about records: the names of the kinds of
// record a change touches, the link to each record, and one way to send a
// change that reports a conflict in words.
import { useState, type MouseEvent, type ReactNode } from "react";
import { ApiError, type Activity, type OwnerQuestion } from "../../api";
import { useWorkspace } from "../../state";

export type Open = (id: string) => void;
export interface Links {
  onOpenJob: Open;
  onOpenApplication: Open;
}

export const subjectNames: Record<string, string> = {
  job: "Job",
  application: "Application",
  knowledge: "Career entry",
  claim: "Claim",
  template: "Template",
  source: "Source",
  collection_run: "Collection run",
  collection: "Collection settings",
  provider: "Provider",
  task: "Collection task",
  profile: "Profile",
  note: "Note",
  context: "Context",
  document: "Document",
  file: "File",
  question: "Question",
  request: "Request",
  preferences: "Preferences",
  settings: "Settings",
  token: "API token",
  workspace: "Workspace",
  skill: "Skill",
};

/** The kinds of change the timeline filters by, each a set of record kinds. */
export const changeGroups = [
  { id: "jobs", label: "Jobs", types: ["job"] },
  { id: "applications", label: "Applications", types: ["application"] },
  {
    id: "documents",
    label: "Documents",
    types: ["document", "context", "file"],
  },
  {
    id: "career",
    label: "Career and templates",
    types: ["knowledge", "claim", "profile", "template"],
  },
  {
    id: "preferences",
    label: "Preferences",
    types: ["preferences", "settings"],
  },
  {
    id: "collection",
    label: "Collection",
    types: ["source", "collection_run", "collection", "provider", "task"],
  },
  { id: "notes", label: "Notes", types: ["note"] },
  {
    id: "agent",
    label: "Questions and requests",
    types: ["question", "request"],
  },
  {
    id: "settings",
    label: "Settings and skills",
    types: ["token", "workspace", "skill"],
  },
];
export const groupOf = (type?: string | null) =>
  changeGroups.find((group) => group.types.includes(type || ""));

/** The screen that shows a record which is not a job or an application. */
function screenOf(type: string, id?: string | null) {
  const routes: Record<string, string> = {
    knowledge: id ? `#career?entry=${id}` : "#career?section=knowledge",
    claim: "#career?section=claims",
    profile: "#career",
    template: id ? `#templates?template=${id}` : "#templates",
    preferences: "#preferences",
    settings: "#preferences",
    source: "#collection",
    collection: "#collection",
    collection_run: "#collection?section=runs",
    provider: "#collection?section=providers",
    task: "#collection?section=runs&view=tasks",
    token: "#settings?section=agents",
    workspace: "#settings?section=workspace",
    skill: id
      ? `#settings?section=skills&skill=${encodeURIComponent(id)}`
      : "#settings?section=skills",
  };
  return routes[type];
}

const plain = (event: MouseEvent) =>
  !event.button &&
  !event.metaKey &&
  !event.ctrlKey &&
  !event.shiftKey &&
  !event.altKey;

/**
 * The link to the record something is about. A job or an application opens
 * over the current screen; its address also works on its own.
 */
export function RecordLink({
  type,
  id,
  jobId,
  applicationId,
  label,
  named = true,
  onOpenJob,
  onOpenApplication,
}: Links & {
  type?: string | null;
  id?: string | null;
  jobId?: string | null;
  applicationId?: string | null;
  label?: string;
  /** Say the kind of record before its name: "Job: Data engineer". */
  named?: boolean;
}): ReactNode {
  const name = subjectNames[type || ""] || "Record";
  const text = label ? (named ? `${name}: ${label}` : label) : name;
  const open = (href: string, action: () => void) => (
    <a
      href={href}
      onClick={(event) => {
        if (!plain(event)) return;
        event.preventDefault();
        action();
      }}
    >
      {text}
    </a>
  );
  if (applicationId)
    return open(`#review?application=${applicationId}`, () =>
      onOpenApplication(applicationId),
    );
  if (jobId) return open(`#jobs?job=${jobId}`, () => onOpenJob(jobId));
  const screen = type && id ? screenOf(type, id) : undefined;
  if (screen) return <a href={screen}>{text}</a>;
  return type ? text : null;
}

/** The record a question or a request is about, or its name once it is deleted. */
export function SubjectLink({
  subject,
  ...links
}: Links & { subject: OwnerQuestion["subject"] }): ReactNode {
  if (!subject) return null;
  if (subject.deleted)
    return `${subjectNames[subject.type]}: ${subject.label} (deleted)`;
  return (
    <RecordLink
      {...links}
      type={subject.type}
      id={subject.id}
      jobId={subject.type === "job" ? subject.id : null}
      applicationId={subject.type === "application" ? subject.id : null}
      label={subject.label}
    />
  );
}

/** The record a change touched; a deleted job or application has none to open. */
export function ChangeSubject({
  event,
  named,
  ...links
}: Links & { event: Activity; named?: boolean }): ReactNode {
  return (
    <RecordLink
      {...links}
      named={named}
      type={event.subject?.type}
      id={event.subject?.id}
      jobId={event.kind === "job_forgotten" ? null : event.job_id || null}
      applicationId={
        event.kind === "application_deleted"
          ? null
          : event.application_id || null
      }
      label={event.subject?.label}
    />
  );
}

export type Outcome = "ok" | "conflict" | "error";
/**
 * Send one change. A version conflict reads the records again (`reload`) and
 * says so; whatever the owner typed stays in the open form.
 */
export function useAct(reload: () => void) {
  const { notify } = useWorkspace();
  const [busy, setBusy] = useState(false);
  async function act(
    call: () => Promise<unknown>,
    message: string,
  ): Promise<Outcome> {
    setBusy(true);
    try {
      await call();
      notify(message);
      return "ok";
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        reload();
        notify(
          cause.code === "conflict"
            ? "This changed in another session. The latest version is shown and your text is kept: check it and try again."
            : cause.message,
          true,
        );
        return "conflict";
      }
      notify(
        cause instanceof Error ? cause.message : "The change was not saved.",
        true,
      );
      return "error";
    } finally {
      setBusy(false);
    }
  }
  return { act, busy };
}
