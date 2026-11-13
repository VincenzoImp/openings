// What the review page derives from an application and its revisions. No
// React: tested directly.
import type { Application, Document, WorkspaceFile } from "../../api";

export const kindLabels: Record<string, string> = {
  resume: "CV",
  cover_letter: "Letter",
  answers: "Form answers",
  other: "Other",
};

/** The current revisions: those no later revision replaces, newest first. */
export function currentRevisions<T extends Pick<Document, "id" | "created_at">>(
  revisions: (T & { previous_id?: string | null })[],
) {
  const replaced = new Set(
    revisions.map((item) => item.previous_id).filter(Boolean),
  );
  return revisions
    .filter((item) => !replaced.has(item.id))
    .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
}

/** The current revision of one kind: the CV or the letter the owner sends. */
export function currentOf<
  T extends Pick<Document, "id" | "kind" | "created_at">,
>(revisions: (T & { previous_id?: string | null })[], kind: string) {
  return currentRevisions(revisions).find((item) => item.kind === kind) || null;
}

export const isPdf = (file: WorkspaceFile) =>
  file.media_type === "application/pdf" || /\.pdf$/i.test(file.name);
export const isSource = (file: WorkspaceFile) =>
  /\.(tex|ltx|md|txt)$/i.test(file.name) ||
  ["application/x-tex", "text/x-tex", "text/markdown"].includes(
    file.media_type,
  );

export interface Notice {
  /** The tab that settles it. */
  tab: "answers" | "requirements";
  text: string;
}

/**
 * "Before you send": what the form or the employer still asks for, from the
 * unresolved requirements and the required questions without an answer.
 */
export function beforeYouSend(app: Application): Notice[] {
  if (app.status !== "draft") return [];
  const notices: Notice[] = [];
  const empty = (app.questions || []).filter((question) => {
    if (!question.required) return false;
    const answer = app.answers?.[question.id];
    return answer === undefined || answer === null || answer === "";
  });
  if (empty.length)
    notices.push({
      tab: "answers",
      text:
        empty.length === 1
          ? `the form asks for "${empty[0].label}" and it has no answer`
          : `${empty.length} required answers of the form are empty`,
    });
  const open = (app.requirements || []).filter((item) => !item.resolved);
  if (open.length)
    notices.push({
      tab: "requirements",
      text:
        open.length === 1
          ? `one requirement is not resolved: ${open[0].text}`
          : `${open.length} requirements are not resolved${
              open.some((item) => item.blocking)
                ? ", some of them blocking"
                : ""
            }`,
    });
  return notices;
}

/** Where an application stands in the Ready queue, and the next one. */
export function queuePlace<T extends { id: string }>(queue: T[], id: string) {
  const index = queue.findIndex((item) => item.id === id);
  if (index < 0) return null;
  return {
    position: index + 1,
    total: queue.length,
    next: queue[index + 1] || null,
  };
}

/** The tab an address of the old application drawer (`detail=`) meant. */
export function tabOf(value: string) {
  const old: Record<string, string> = {
    history: "timeline",
    documents: "documents",
    requirements: "requirements",
    answers: "answers",
    details: "details",
    posting: "answers",
  };
  return TABS.includes(value) ? value : old[value] || "answers";
}
export const TABS = [
  "answers",
  "requirements",
  "timeline",
  "inputs",
  "documents",
  "details",
];
