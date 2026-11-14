import { useEffect, useRef, useState } from "react";
import {
  api,
  date,
  downloadWorkspaceFile,
  fileUrl,
  uploadFile,
  type ListResult,
  type WorkspaceFile,
} from "../api";
import { Button, Dialog, ErrorBanner, Loading } from "../design";
import { useWorkspace } from "../state";
import { ConfirmDialog, fileSize } from "./common";
import { useFresh } from "./useFresh";

const TEXT_TYPES = [
  "text/plain",
  "text/markdown",
  "text/x-tex",
  "application/x-tex",
  "application/json",
];
const kindOf = (file: WorkspaceFile) =>
  file.media_type === "application/pdf" || /\.pdf$/i.test(file.name)
    ? "PDF"
    : /\.(tex|cls|sty)$/i.test(file.name)
      ? "LaTeX"
      : /\.(otf|ttf|woff2?)$/i.test(file.name)
        ? "Font"
        : file.media_type.startsWith("image/")
          ? "Image"
          : file.media_type.startsWith("text/")
            ? "Text"
            : "File";

/** The files of a Career entry, a template or a job, with the path to the list. */
export function useAssets(ownerType: string, ownerId: string) {
  return useFresh<ListResult<WorkspaceFile>>(
    `/files?owner_type=${ownerType}&owner_id=${ownerId}&limit=200`,
    { items: [], total: 0 },
    ["files"],
  );
}
export const isPdf = (file: WorkspaceFile) => kindOf(file) === "PDF";

/**
 * Files attached to a record: open, download, remove and add.
 */
export function Assets({
  ownerType,
  ownerId,
  empty,
  note,
}: {
  ownerType: "career" | "template" | "job";
  ownerId: string;
  /** What to say when there is no file yet. */
  empty: string;
  /** A sentence beside the add button. */
  note?: string;
}) {
  const { data, loading, error, reload } = useAssets(ownerType, ownerId);
  const { mutate, pending, notify } = useWorkspace();
  const [opened, setOpened] = useState<WorkspaceFile | null>(null);
  const [removing, setRemoving] = useState<WorkspaceFile | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const fail = (cause: unknown) =>
    notify(cause instanceof Error ? cause.message : String(cause), true);
  async function add(files: FileList | null) {
    const chosen = Array.from(files || []);
    if (!chosen.length) return;
    await mutate(
      async () => {
        for (const file of chosen) await uploadFile(file, ownerType, ownerId);
      },
      chosen.length === 1 ? "File added." : `${chosen.length} files added.`,
    );
  }
  return (
    <>
      {error ? (
        <div className="body">
          <ErrorBanner message={error} retry={reload} />
        </div>
      ) : loading ? (
        <Loading label="Loading files…" />
      ) : data.items.length ? (
        <div className="datatable-wrap">
          <table className="datatable stack">
            <thead>
              <tr>
                <th>File</th>
                <th>Kind</th>
                <th className="right">Size</th>
                <th>Added</th>
                <th>
                  <span className="sr">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((file) => (
                <tr key={file.id}>
                  <td className="primary">
                    <button
                      type="button"
                      className="link mono"
                      onClick={() => setOpened(file)}
                    >
                      {file.name}
                    </button>
                  </td>
                  <td className="meta" data-label="Kind">
                    {kindOf(file)}
                  </td>
                  <td className="right num meta" data-label="Size">
                    {fileSize(file.size)}
                  </td>
                  <td className="meta" data-label="Added">
                    {date(file.created_at)}
                  </td>
                  <td className="actions">
                    <Button
                      size="sm"
                      variant="quiet"
                      aria-label={`Download ${file.name}`}
                      onClick={() => downloadWorkspaceFile(file).catch(fail)}
                    >
                      Download
                    </Button>
                    <Button
                      size="sm"
                      variant="quiet danger"
                      aria-label={`Remove ${file.name}`}
                      disabled={pending}
                      onClick={() => setRemoving(file)}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="body muted">{empty}</p>
      )}
      <footer>
        <span className="muted grow">{note}</span>
        <input
          ref={picker}
          type="file"
          multiple
          hidden
          aria-label="Files to add"
          onChange={(event) => {
            void add(event.target.files);
            event.target.value = "";
          }}
        />
        <Button
          size="sm"
          icon="upload"
          disabled={pending}
          onClick={() => picker.current?.click()}
        >
          Add files
        </Button>
      </footer>
      {opened && <FileDialog file={opened} onClose={() => setOpened(null)} />}
      {removing && (
        <ConfirmDialog
          title="Remove this file?"
          confirm="Remove file"
          keep="Keep file"
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/files/${removing.id}?expected_version=${removing.version ?? 1}`,
                    "DELETE",
                  ),
                "File removed.",
              )
            )
              setRemoving(null);
          }}
        >
          <p>
            <strong className="mono">{removing.name}</strong> is removed from
            this record. Applications that were already prepared keep their own
            copy.
          </p>
        </ConfirmDialog>
      )}
    </>
  );
}

/** A file opened in place: PDF, image or text, with its facts and a download. */
export function FileDialog({
  file,
  onClose,
}: {
  file: WorkspaceFile;
  onClose: () => void;
}) {
  const { notify } = useWorkspace();
  const [url, setUrl] = useState("");
  const [content, setContent] = useState<string | null>(null);
  const [facts, setFacts] = useState<WorkspaceFile>(file);
  const [error, setError] = useState("");
  const pdf = isPdf(file);
  const image = ["image/png", "image/jpeg", "image/webp"].includes(
    file.media_type,
  );
  const plain = TEXT_TYPES.includes(file.media_type) && file.size <= 1_000_000;
  useEffect(() => {
    const abort = new AbortController();
    api<WorkspaceFile>(`/files/${file.id}`, "GET", undefined, abort.signal)
      .then(setFacts)
      .catch(() => {});
    if (pdf || image || plain)
      fileUrl(file)
        .then(async (value) => {
          if (!plain) return abort.signal.aborted || setUrl(value);
          const response = await fetch(value, { signal: abort.signal });
          if (!response.ok) throw Error("Unable to read this file.");
          setContent(await response.text());
        })
        .catch((cause) => {
          if (!abort.signal.aborted)
            setError(
              cause instanceof Error ? cause.message : "Preview failed.",
            );
        });
    return () => abort.abort();
  }, [file.id]);
  return (
    <Dialog
      className="wide"
      title={file.name}
      onClose={onClose}
      footer={
        <>
          <Button
            icon="download"
            onClick={() =>
              downloadWorkspaceFile(file).catch((cause) =>
                notify(String(cause), true),
              )
            }
          >
            Download
          </Button>
          <Button onClick={onClose}>Close</Button>
        </>
      }
    >
      <div className="stack">
        {error ? (
          <ErrorBanner message={error} />
        ) : pdf || image ? (
          !url ? (
            <Loading label="Loading the file…" />
          ) : pdf ? (
            <iframe
              title={`Preview of ${file.name}`}
              className="frame"
              src={url}
              referrerPolicy="no-referrer"
            />
          ) : (
            <img className="frame" src={url} alt={file.name} />
          )
        ) : plain ? (
          content === null ? (
            <Loading label="Loading the file…" />
          ) : (
            <pre
              className="code"
              tabIndex={0}
              role="region"
              aria-label={file.name}
            >
              {content}
            </pre>
          )
        ) : (
          <p className="muted">
            This kind of file cannot be shown here. Download it to open it on
            your device.
          </p>
        )}
        <dl className="dl">
          <dt>Kind</dt>
          <dd>{facts.media_type}</dd>
          <dt>Size</dt>
          <dd className="num">{facts.size.toLocaleString("en")} bytes</dd>
          <dt>Added</dt>
          <dd>{date(facts.created_at)}</dd>
          <dt>SHA-256</dt>
          <dd className="mono">{facts.sha256 || "Not available"}</dd>
        </dl>
      </div>
    </Dialog>
  );
}
