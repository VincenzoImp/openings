// What the review page derives from an application and its revisions. No
// React: tested directly.
import type { Application, Document, WorkspaceFile } from "../../api";

export const kindLabels: Record<string, string> = {
  cv: "CV",
  letter: "Letter",
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
/** A TeX source, as the server reads it: by name or media type. */
export const isSource = (file: WorkspaceFile) =>
  /\.(tex|ltx)$/i.test(file.name) ||
  [
    "application/x-tex",
    "text/x-tex",
    "application/x-latex",
    "text/x-latex",
  ].includes(file.media_type.split(";")[0]);

/** A CV or letter is its PDF and an optional .tex source; other kinds keep structured content. */
export const SOURCE_KINDS = ["cv", "letter"];
export const isSourceKind = (kind: string) => SOURCE_KINDS.includes(kind);

/** The source and the PDF of a revision, and how the PDF names its source. */
export function sourceAndPdf(revision: Pick<Document, "files">) {
  const files = revision.files || [];
  const source = files.find(isSource) || null;
  const pdf = files.find(isPdf) || null;
  const pairing = !pdf
    ? null
    : !pdf.source_sha256
      ? "unnamed"
      : source && pdf.source_sha256 === source.sha256
        ? "matches"
        : "other";
  return { source, pdf, pairing };
}

/** Why a CV or letter revision is not complete yet, or null when it is. */
export function incompleteReason(revision: Pick<Document, "kind" | "files">) {
  if (!isSourceKind(revision.kind)) return null;
  const { pdf } = sourceAndPdf(revision);
  return pdf ? null : "Upload its PDF: until then it does not count for Ready.";
}

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
  if (app.status !== "shortlisted") return [];
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

/**
 * The Ready application to review after `id` is marked applied: the one after
 * it in the queue, or the first other one when it was the last or not listed.
 */
export function nextReady<T extends { id: string }>(queue: T[], id: string) {
  const index = queue.findIndex((item) => item.id === id);
  const others = queue.filter((item) => item.id !== id);
  if (!others.length) return null;
  return index < 0 ? others[0] : queue[index + 1] || others[0];
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
    // The Inputs tab is gone; its old links open the documents.
    inputs: "documents",
  };
  return TABS.includes(value) ? value : old[value] || "answers";
}
export const TABS = [
  "answers",
  "requirements",
  "timeline",
  "documents",
  "details",
];
