import { useRef, useState } from "react";
import {
  api,
  uploadFile,
  type Application,
  type Consistency,
  type Document,
  type ListResult,
  type WorkspaceFile,
} from "../../api";
import {
  Banner,
  Button,
  ErrorBanner,
  Loading,
  Tag,
  ValueTree,
} from "../../design";
import { FileDialog } from "../../library/Assets";
import { ConfirmDialog, Pager, fileSize } from "../../library/common";
import { dayTime } from "../../library/time";
import {
  useDebounce,
  useResource,
  useUrlFilters,
  useWorkspace,
} from "../../state";
import { kindLabels } from "./model";
import { RevisionDialog } from "./RevisionDialog";

const NONE = { items: [], total: 0 };

function Check({ report }: { report: Consistency }) {
  if (report.status === "consistent")
    return <p className="caption">{report.reason}</p>;
  if (report.status === "not_checked")
    return <p className="caption">{report.reason}</p>;
  return (
    <Banner tone="attention" title="The saved text and the .tex source differ">
      <p>{report.reason}</p>
      <ul className="plain">
        {report.mismatches.slice(0, 5).map((item) => (
          <li key={item.path}>
            <span className="mono">{item.path}</span> {item.text}
          </li>
        ))}
      </ul>
    </Banner>
  );
}

/** One revision opened: its text, files, source check and the actions on it. */
function Detail({
  application,
  summary,
}: {
  application: Application;
  summary: Document;
}) {
  const { mutate, pending } = useWorkspace();
  const detail = useResource<Document | null>(`/documents/${summary.id}`, null);
  const check = useResource<Consistency | null>(
    `/documents/${summary.id}/consistency`,
    null,
  );
  const [opened, setOpened] = useState<WorkspaceFile | null>(null);
  const [revising, setRevising] = useState(false);
  const [removing, setRemoving] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const document = detail.data;
  if (detail.error)
    return <ErrorBanner message={detail.error} retry={detail.reload} />;
  if (!document) return <Loading label="Loading the revision…" />;
  const approved = document.review_state === "approved";
  const mismatch = check.data?.status === "mismatch";
  return (
    <div className="stack revision">
      {typeof document.content.text === "string" ? (
        <div className="paper">{document.content.text || "No text."}</div>
      ) : (
        <ValueTree value={document.content} />
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
            <span className="caption num">{fileSize(file.size)}</span>
          </li>
        ))}
        {!document.files?.length && <li className="muted">No file yet.</li>}
      </ul>
      {check.data && <Check report={check.data} />}
      <div className="row">
        {!approved && (
          <>
            <input
              ref={picker}
              type="file"
              hidden
              aria-label="File to add to the revision"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file)
                  void mutate(
                    () => uploadFile(file, "document", document.id),
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
              Add a file
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={pending || check.loading}
              onClick={() =>
                void mutate(
                  () =>
                    api(`/documents/${document.id}/review`, "POST", {
                      review_state: "approved",
                      expected_version: document.version,
                      allow_content_mismatch: mismatch,
                    }),
                  "Revision approved.",
                )
              }
            >
              {mismatch ? "Approve with differences" : "Approve this revision"}
            </Button>
          </>
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
                () => api(`/documents/${document.id}`, "DELETE"),
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

/** Every document revision of the application: find, open, approve, revise, delete. */
export function Revisions({ application }: { application: Application }) {
  const [filters, setFilters] = useUrlFilters({
    doc_q: "",
    doc_kind: "",
    doc_review: "",
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
  if (filters.doc_review) query.set("review_state", filters.doc_review);
  const list = useResource<ListResult<Document>>(`/documents?${query}`, NONE);
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  return (
    <div className="stack">
      <div className="filterbar" role="group" aria-label="Find a revision">
        <input
          className="input"
          type="search"
          aria-label="Search revisions by title"
          placeholder="Search by title"
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
        <select
          className="input"
          aria-label="Review state"
          value={filters.doc_review}
          onChange={(event) =>
            setFilters({ doc_review: event.target.value, doc_offset: "0" })
          }
        >
          <option value="">Approved or not</option>
          <option value="draft">Not approved</option>
          <option value="approved">Approved</option>
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
              <Tag
                tone={item.review_state === "approved" ? "ready" : undefined}
              >
                {item.review_state === "approved" ? "Approved" : "Not approved"}
              </Tag>
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
          {q || filters.doc_kind || filters.doc_review
            ? "No revision matches."
            : "No document yet. Your agent saves the CV and the letter here."}
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
