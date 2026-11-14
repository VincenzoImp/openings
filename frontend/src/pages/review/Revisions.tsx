import { useRef, useState } from "react";
import {
  api,
  uploadFile,
  type Application,
  type Comparison,
  type Document,
  type ListResult,
  type WorkspaceFile,
} from "../../api";
import {
  Button,
  ErrorBanner,
  Loading,
  Tag,
  TextDiff,
  ValueTree,
} from "../../design";
import { FileDialog } from "../../library/Assets";
import { ConfirmDialog, Pager, fileSize } from "../../library/common";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import {
  useDebounce,
  useResource,
  useUrlFilters,
  useWorkspace,
} from "../../state";
import {
  incompleteReason,
  isPdf,
  isSource,
  isSourceKind,
  kindLabels,
  sourceAndPdf,
} from "./model";
import { RevisionDialog } from "./RevisionDialog";

const NONE = { items: [], total: 0 };

/** The revision's text compared with the one it replaces. */
function Changes({ document }: { document: Document }) {
  const result = useResource<Comparison | null>(
    `/documents/${document.id}/comparison`,
    null,
  );
  if (result.error)
    return <ErrorBanner message={result.error} retry={result.reload} />;
  if (!result.data) return <Loading label="Comparing the revisions…" />;
  const { added, removed, lines, text } = result.data;
  const previous = (document.revision_number || 2) - 1;
  if (!text.document || !text.other)
    return (
      <p className="caption">
        {text.document ? `Revision ${previous}` : "This revision"} has no
        readable text, so there is nothing to compare.
      </p>
    );
  return (
    <div className="stack">
      <p className="caption" role="status">
        {added || removed
          ? `Since revision ${previous}: ${added} ${added === 1 ? "line" : "lines"} added, ${removed} removed.`
          : `The text is the same as in revision ${previous}.`}
      </p>
      {(added > 0 || removed > 0) && (
        <TextDiff lines={lines} label={`Changes since revision ${previous}`} />
      )}
    </div>
  );
}

/** What a file is to its revision: the source, the PDF and what it was built from. */
function role(document: Document, file: WorkspaceFile) {
  if (isSource(file)) return "Source";
  if (!isPdf(file)) return "";
  const { pairing, source } = sourceAndPdf(document);
  if (pairing === "matches") return `PDF, built from ${source?.name}`;
  if (pairing === "unnamed") return "PDF";
  return "PDF of another source";
}

/** One revision opened: its text, files and evidence, the comparison and the actions on it. */
function Detail({
  application,
  summary,
}: {
  application: Application;
  summary: Document;
}) {
  const { mutate, pending } = useWorkspace();
  // Read again after any change of documents or files, replacing what was shown.
  const detail = useFresh<Document | null>(`/documents/${summary.id}`, null, [
    "documents",
    "files",
  ]);
  const [opened, setOpened] = useState<WorkspaceFile | null>(null);
  const [revising, setRevising] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [comparing, setComparing] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const document = detail.data;
  if (detail.error)
    return <ErrorBanner message={detail.error} retry={detail.reload} />;
  if (!document) return <Loading label="Loading the revision…" />;
  const sourceKind = isSourceKind(document.kind);
  const { source, pdf } = sourceAndPdf(document);
  // A complete CV or letter (its PDF stored) never changes: a change is a new revision.
  const complete = sourceKind ? !!pdf : false;
  const incomplete = incompleteReason(document);
  const claims = document.claim_ids?.length || 0;
  const entries = document.knowledge_ids?.length || 0;
  return (
    <div className="stack revision">
      {sourceKind ? (
        document.text ? (
          <div
            className="paper"
            role="document"
            aria-label={`Text of revision ${document.revision_number || 1}`}
          >
            {document.text}
          </div>
        ) : (
          <p className="muted">
            {source
              ? "The source has no readable text."
              : pdf
                ? "No text could be read from the PDF. The PDF is the document."
                : "No PDF yet. Upload it, with the .tex source it was built from if you have one."}
          </p>
        )
      ) : typeof document.content?.text === "string" ? (
        <div className="paper">{document.content.text || "No text."}</div>
      ) : (
        <ValueTree value={document.content || {}} />
      )}
      {sourceKind && document.text && (
        <p className="caption">
          Text read from{" "}
          <span className="mono">
            {document.text_from === "pdf" ? pdf?.name : source?.name}
          </span>
          , without its layout. The PDF shows the layout.
        </p>
      )}
      {document.note && <p>{document.note}</p>}
      {(claims > 0 || entries > 0) && (
        <p className="caption">
          Cites {claims} {claims === 1 ? "claim" : "claims"} and {entries}{" "}
          {entries === 1 ? "Career entry" : "Career entries"}.
        </p>
      )}
      <ul className="list" aria-label="Files of the revision">
        {(document.files || []).map((file) => (
          <li key={file.id}>
            <button
              type="button"
              className="link mono grow"
              onClick={() => setOpened(file)}
            >
              {file.name}
            </button>
            {role(document, file) && (
              <span className="caption">{role(document, file)}</span>
            )}
            <span className="caption num">{fileSize(file.size)}</span>
          </li>
        ))}
        {!document.files?.length && <li className="muted">No file yet.</li>}
      </ul>
      {comparing && <Changes document={document} />}
      {incomplete && <p className="caption">{incomplete}</p>}
      <div className="row">
        {!complete && (
          <>
            <input
              ref={picker}
              type="file"
              hidden
              aria-label={
                sourceKind && !pdf
                  ? "PDF or source to upload"
                  : "File to add to the revision"
              }
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file)
                  void mutate(
                    () =>
                      uploadFile(
                        file,
                        "document",
                        document.id,
                        /\.pdf$/i.test(file.name)
                          ? document.source_sha256
                          : null,
                      ),
                    "File added.",
                  );
              }}
            />
            <Button
              size="sm"
              icon="upload"
              disabled={pending}
              onClick={() => picker.current?.click()}
            >
              {sourceKind && !pdf ? "Upload PDF or .tex" : "Add a file"}
            </Button>
          </>
        )}
        {document.previous_id && (
          <Button
            size="sm"
            aria-expanded={comparing}
            onClick={() => setComparing(!comparing)}
          >
            {comparing
              ? "Hide the changes"
              : `Compare with revision ${(document.revision_number || 2) - 1}`}
          </Button>
        )}
        <Button size="sm" onClick={() => setRevising(true)}>
          New revision
        </Button>
        <Button
          size="sm"
          variant="quiet danger"
          onClick={() => setRemoving(true)}
        >
          Delete revision
        </Button>
      </div>
      {opened && <FileDialog file={opened} onClose={() => setOpened(null)} />}
      {revising && (
        <RevisionDialog
          application={application}
          previous={document}
          onClose={() => setRevising(false)}
        />
      )}
      {removing && (
        <ConfirmDialog
          title="Delete this revision?"
          confirm="Delete the revision"
          keep="Keep the revision"
          onClose={() => setRemoving(false)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/documents/${document.id}?expected_version=${document.version}`,
                    "DELETE",
                  ),
                "Revision deleted.",
              )
            )
              setRemoving(false);
          }}
        >
          <p>
            Revision {document.revision_number || 1} of{" "}
            {document.title || "this document"} and its files are removed for
            good. Other revisions stay.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}

/** Every document revision of the application: find, open, upload, compare, revise, delete. */
export function Revisions({ application }: { application: Application }) {
  const [filters, setFilters] = useUrlFilters({
    doc_q: "",
    doc_kind: "",
    doc_offset: "0",
  });
  const q = useDebounce(filters.doc_q);
  const offset = Number(filters.doc_offset) || 0;
  const query = new URLSearchParams({
    application_id: application.id,
    summary: "true",
    limit: "20",
    offset: String(offset),
  });
  if (q) query.set("q", q);
  if (filters.doc_kind) query.set("kind", filters.doc_kind);
  // The list is read again after every document or file change (a new revision
  // and its uploads), whatever form is open.
  const list = useFresh<ListResult<Document>>(`/documents?${query}`, NONE, [
    "documents",
    "files",
  ]);
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  return (
    <div className="stack">
      <div className="filterbar" role="group" aria-label="Find a revision">
        <input
          className="input"
          type="search"
          aria-label="Search revisions by title or text"
          placeholder="Search titles and text"
          value={filters.doc_q}
          onChange={(event) =>
            setFilters({ doc_q: event.target.value, doc_offset: "0" })
          }
        />
        <select
          className="input"
          aria-label="Kind of document"
          value={filters.doc_kind}
          onChange={(event) =>
            setFilters({ doc_kind: event.target.value, doc_offset: "0" })
          }
        >
          <option value="">Every kind</option>
          {Object.entries(kindLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <Button size="sm" icon="plus" onClick={() => setAdding(true)}>
          Add a document
        </Button>
      </div>
      {list.error && <ErrorBanner message={list.error} retry={list.reload} />}
      {list.loading ? (
        <Loading label="Loading the revisions…" />
      ) : list.data.items.length ? (
        <ul className="list" aria-label="Document revisions">
          {list.data.items.map((item) => (
            <li key={item.id} className="wrap revision-row">
              <div className="grow">
                <div className="title">
                  {kindLabels[item.kind] || item.kind} ·{" "}
                  {item.title || "Untitled"}
                </div>
                <div className="meta">
                  Revision {item.revision_number || 1} ·{" "}
                  {dayTime(item.created_at)} ·{" "}
                  {item.file_count ? `${item.file_count} files` : "no file"}
                </div>
              </div>
              {isSourceKind(item.kind) && (
                <Tag tone={item.complete ? "ready" : "attention"}>
                  {item.complete ? "Complete" : "Without PDF"}
                </Tag>
              )}
              <Button
                size="sm"
                variant="quiet"
                aria-expanded={open === item.id}
                onClick={() => setOpen(open === item.id ? null : item.id)}
              >
                {open === item.id ? "Close" : "Open"}
                <span className="sr"> {item.title || "revision"}</span>
              </Button>
              {open === item.id && (
                <Detail application={application} summary={item} />
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">
          {q || filters.doc_kind
            ? "No revision matches."
            : "No document yet. Upload the CV and the letter here."}
        </p>
      )}
      <Pager
        offset={offset}
        total={list.data.total}
        limit={20}
        label="Revision pages"
        onChange={(next) => setFilters({ doc_offset: String(next) })}
      />
      {adding && (
        <RevisionDialog
          application={application}
          onClose={() => setAdding(false)}
        />
      )}
    </div>
  );
}
