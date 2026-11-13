import { useState } from "react";
import {
  api,
  download,
  downloadWorkspaceFile,
  type Application,
  type Json,
  type ListResult,
  type Staleness,
  type WorkspaceFile,
} from "../../api";
import { Button, ErrorBanner, Loading, Tag } from "../../design";
import { Pager, plural } from "../../library/common";
import {
  changeName,
  changeState,
  comparisonNotes,
  concerned,
} from "../../library/staleness";
import { dayTime } from "../../library/time";
import { useResource, useWorkspace } from "../../state";
import { ContextDialog } from "./ContextDialog";
import { kindLabels } from "./model";

const NONE = { items: [], total: 0 };

/** What changed in the record since the current revisions were written. */
function Changes({ report }: { report: Staleness }) {
  const stale = report.documents.filter((item) => item.status === "stale");
  return (
    <div className="stack">
      <ul
        className="list"
        aria-label="Inputs changed since the documents were written"
      >
        {report.changes.map((change) => {
          const only = concerned(change, report, kindLabels);
          return (
            <li key={`${change.input}-${change.id ?? ""}`}>
              <span className="grow">{changeName(change)}</span>
              <span className="caption">
                {changeState(change)}
                {only ? ` · ${only} only` : ""}
              </span>
            </li>
          );
        })}
      </ul>
      {stale.length > 0 && (
        <p className="caption">
          Written from the older inputs:{" "}
          {stale
            .map((item) => item.title || kindLabels[item.kind] || item.kind)
            .join(", ")}
        </p>
      )}
    </div>
  );
}

/** The comparison of the frozen copies the current revisions use. */
function Comparison({
  application,
  stale,
}: {
  application: Application;
  stale: boolean;
}) {
  const report = useResource<Staleness | null>(
    `/applications/${application.id}/staleness`,
    null,
  );
  if (report.error)
    return <ErrorBanner message={report.error} retry={report.reload} />;
  if (!report.data)
    return stale ? <Loading label="Comparing the inputs…" /> : null;
  const notes = comparisonNotes(report.data);
  return (
    <>
      {report.data.changes.length > 0 && <Changes report={report.data} />}
      {notes.map((note) => (
        <p key={note} className="caption">
          {note}
        </p>
      ))}
    </>
  );
}

function ContextFiles({ id }: { id: string }) {
  const { notify } = useWorkspace();
  const files = useResource<ListResult<WorkspaceFile>>(
    `/files?owner_type=context&owner_id=${id}&limit=200`,
    NONE,
  );
  if (files.error)
    return <ErrorBanner message={files.error} retry={files.reload} />;
  if (files.loading) return <Loading label="Loading the files…" />;
  if (!files.data.items.length)
    return <p className="caption">No file in this copy.</p>;
  return (
    <ul className="plain">
      {files.data.items.map((file) => (
        <li key={file.id}>
          <button
            type="button"
            className="link mono"
            onClick={() =>
              downloadWorkspaceFile(file).catch((cause) =>
                notify(String(cause), true),
              )
            }
          >
            {file.name}
          </button>
        </li>
      ))}
    </ul>
  );
}

/**
 * The frozen copies of the record the documents were written from, whether
 * what they froze has changed since, and a new copy for the agent.
 */
export function Inputs({ application }: { application: Application }) {
  const { notify } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const [preparing, setPreparing] = useState(false);
  const [openFiles, setOpenFiles] = useState<string | null>(null);
  const contexts = useResource<ListResult<Json>>(
    `/contexts?application_id=${application.id}&summary=true&limit=20&offset=${offset}`,
    NONE,
  );
  const stale = application.stale_inputs?.length;
  async function save(id: string) {
    try {
      const data = await api<Json>(`/contexts/${id}`);
      download(`context-${id}.json`, JSON.stringify(data, null, 2));
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : "Download failed.", true);
    }
  }
  return (
    <div className="stack">
      <div className="spread wrap">
        <p>
          The documents are written from a frozen copy of your record.{" "}
          {stale ? (
            <Tag tone="attention">Inputs changed since</Tag>
          ) : (
            <Tag tone="ready">Inputs are current</Tag>
          )}
        </p>
        <Button size="sm" icon="download" onClick={() => setPreparing(true)}>
          Prepare a frozen copy
        </Button>
      </div>
      <Comparison application={application} stale={Boolean(stale)} />
      {contexts.error && (
        <ErrorBanner message={contexts.error} retry={contexts.reload} />
      )}
      {contexts.loading ? (
        <Loading label="Loading the frozen copies…" />
      ) : contexts.data.items.length ? (
        <ul className="list" aria-label="Frozen copies">
          {contexts.data.items.map((context) => {
            const id = String(context.id);
            return (
              <li key={id} className="wrap">
                <div className="grow">
                  <div className="title">
                    {dayTime(String(context.created_at))}
                    {context.template_name ? ` · ${context.template_name}` : ""}
                  </div>
                  <div className="meta">
                    {plural(
                      Number(context.knowledge_count || 0),
                      "Career entry",
                      "Career entries",
                    )}
                    {" · "}
                    {plural(Number(context.claim_count || 0), "claim")}
                    {" · "}
                    {plural(Number(context.file_count || 0), "file")}
                    {" · used by "}
                    {plural(Number(context.document_count || 0), "revision")}
                  </div>
                  {openFiles === id && <ContextFiles id={id} />}
                </div>
                <Button
                  size="sm"
                  variant="quiet"
                  aria-expanded={openFiles === id}
                  onClick={() => setOpenFiles(openFiles === id ? null : id)}
                >
                  Files
                </Button>
                <Button size="sm" onClick={() => save(id)}>
                  Download
                  <span className="sr">
                    {" "}
                    the copy of {String(context.created_at)}
                  </span>
                </Button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="muted">No frozen copy yet.</p>
      )}
      <Pager
        offset={offset}
        total={contexts.data.total}
        limit={20}
        label="Frozen copy pages"
        onChange={setOffset}
      />
      {preparing && (
        <ContextDialog
          application={application}
          onClose={() => setPreparing(false)}
        />
      )}
    </div>
  );
}
