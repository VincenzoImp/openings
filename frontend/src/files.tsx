import { useEffect, useMemo, useState } from "react";
import {
  api,
  date,
  downloadWorkspaceFile,
  fileUrl,
  uploadFile,
  type ListResult,
  type WorkspaceFile,
} from "./api";
import { useDebounce, useResource, useWorkspace } from "./state";
import {
  Button,
  Dialog,
  ErrorBox,
  Field,
  Icon,
  Loading,
  Pagination,
  PendingResults,
} from "./ui";
export function FileManager({
  ownerType,
  ownerId,
  immutable = false,
  preview = false,
  readOnly = false,
  files,
}: {
  ownerType: string;
  ownerId: string;
  immutable?: boolean;
  preview?: boolean;
  readOnly?: boolean;
  files?: WorkspaceFile[];
}) {
  const [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0),
    [inspecting, setInspecting] = useState<WorkspaceFile | null>(null);
  const [mediaType, setMediaType] = useState("");
  const [previewing, setPreviewing] = useState<WorkspaceFile | null>(null),
    [removing, setRemoving] = useState<WorkspaceFile | null>(null);
  const debounced = useDebounce(query);
  const resource = useResource<ListResult<WorkspaceFile>>(
    files
      ? null
      : `/files?owner_type=${ownerType}&owner_id=${ownerId}&limit=20&offset=${offset}&q=${encodeURIComponent(debounced)}${mediaType ? `&media_type=${encodeURIComponent(mediaType)}` : ""}`,
    { items: [], total: 0 },
  );
  const data = useMemo(() => {
    if (!files) return resource.data;
    const matching = files.filter(
      (file) =>
        file.name.toLowerCase().includes(debounced.toLowerCase()) &&
        (!mediaType || file.media_type === mediaType),
    );
    return {
      items: matching.slice(offset, offset + 20),
      total: matching.length,
    };
  }, [files, debounced, mediaType, offset, resource.data]);
  const { error, reload } = resource;
  const updating = query !== debounced || (!files && resource.loading);
  const { mutate, pending, notify } = useWorkspace();
  const [pdf, setPdf] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const file = data.items.find(
      (f) =>
        f.media_type === "application/pdf" ||
        f.name.toLowerCase().endsWith(".pdf"),
    );
    setPdf(null);
    if (preview && file)
      fileUrl(file)
        .then((url) => {
          if (active) setPdf(url);
        })
        .catch(() => {});
    return () => {
      active = false;
    };
  }, [data, preview]);
  async function upload(file?: File) {
    if (file)
      await mutate(
        () => uploadFile(file, ownerType, ownerId),
        "File uploaded.",
      );
  }
  return (
    <>
      {error && <ErrorBox message={error} retry={reload} />}
      <PendingResults pending={updating} />
      {(data.total > 5 || query || mediaType) && (
        <div className="file-filters">
          <Field label="Find a file">
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setOffset(0);
              }}
              placeholder="Search file names"
            />
          </Field>
          <Field label="File type">
            <select
              value={mediaType}
              onChange={(e) => {
                setMediaType(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All types</option>
              <option value="application/pdf">PDF</option>
              <option value="text/plain">Plain text</option>
              <option value="application/x-tex">LaTeX</option>
              <option value="image/png">PNG image</option>
              <option value="image/jpeg">JPEG image</option>
            </select>
          </Field>
        </div>
      )}
      <div className="document-files" aria-busy={updating} inert={updating}>
        {data.items.map((file) => (
          <div className="documentrow" key={file.id}>
            <Icon name="file" />
            <div className="doccopy">
              <button
                className="table-link"
                onClick={() => setPreviewing(file)}
              >
                <strong>{file.name}</strong>
              </button>
              <small>
                {Math.max(1, Math.round(file.size / 1024))} KB ·{" "}
                {date(file.created_at)}
              </small>
            </div>
            <button
              className="iconbtn"
              aria-label={`Details for ${file.name}`}
              onClick={() =>
                api<WorkspaceFile>(`/files/${file.id}`)
                  .then(setInspecting)
                  .catch((e) => notify(e.message, true))
              }
            >
              <Icon name="info" />
            </button>
            <button
              className="iconbtn"
              aria-label={`Download ${file.name}`}
              onClick={() =>
                downloadWorkspaceFile(file).catch((e) =>
                  notify(String(e), true),
                )
              }
            >
              <Icon name="download" />
            </button>
            {!immutable && !readOnly && (
              <button
                className="iconbtn danger"
                aria-label={`Delete ${file.name}`}
                disabled={pending}
                onClick={() => setRemoving(file)}
              >
                <Icon name="trash" />
              </button>
            )}
          </div>
        ))}
      </div>
      {previewing && (
        <FilePreview file={previewing} onClose={() => setPreviewing(null)} />
      )}
      {removing && (
        <Dialog title="Delete this file?" onClose={() => setRemoving(null)}>
          <p className="modal-intro">
            Permanently remove {removing.name} from this record. Frozen
            snapshots keep their own copies.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setRemoving(null)}>Keep file</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={async () => {
                if (
                  await mutate(
                    () => api(`/files/${removing.id}`, "DELETE"),
                    "File removed.",
                  )
                )
                  setRemoving(null);
              }}
            >
              Delete file
            </Button>
          </div>
        </Dialog>
      )}
      {(data.total > 20 || offset > 0) && (
        <Pagination
          offset={offset}
          total={data.total}
          limit={20}
          onChange={setOffset}
        />
      )}
      {inspecting && (
        <Dialog title={inspecting.name} onClose={() => setInspecting(null)}>
          <dl className="detailfacts">
            <div>
              <dt>Media type</dt>
              <dd>{inspecting.media_type}</dd>
            </div>
            <div>
              <dt>Size</dt>
              <dd>{inspecting.size.toLocaleString()} bytes</dd>
            </div>
            <div>
              <dt>Added</dt>
              <dd>{date(inspecting.created_at)}</dd>
            </div>
            <div className="full">
              <dt>SHA-256</dt>
              <dd className="hash-value">
                {inspecting.sha256 || "Not available"}
              </dd>
            </div>
          </dl>
          <Button
            icon="download"
            onClick={() =>
              downloadWorkspaceFile(inspecting).catch((e) =>
                notify(e.message, true),
              )
            }
          >
            Download file
          </Button>
        </Dialog>
      )}
      {!readOnly && (
        <label className={`btn upload-button ${pending ? "disabled" : ""}`}>
          <Icon name="upload" />
          {data.items.length ? "Attach another file" : "Upload a file"}
          <input
            className="filepick"
            type="file"
            disabled={pending}
            onChange={(e) => {
              void upload(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </label>
      )}
      {pdf && (
        <iframe
          title="PDF document preview"
          className="pdf-preview"
          src={`${pdf}${pdf.includes("?") ? "&" : "?"}inline=true#toolbar=0`}
          referrerPolicy="no-referrer"
        />
      )}
    </>
  );
}
function FilePreview({
  file,
  onClose,
}: {
  file: WorkspaceFile;
  onClose: () => void;
}) {
  const [url, setUrl] = useState(""),
    [content, setContent] = useState<string | null>(null),
    [error, setError] = useState("");
  const { notify } = useWorkspace();
  const pdf = file.media_type === "application/pdf",
    image = ["image/png", "image/jpeg", "image/webp"].includes(file.media_type),
    plain =
      [
        "text/plain",
        "text/markdown",
        "text/x-tex",
        "application/x-tex",
        "application/json",
      ].includes(file.media_type) && file.size <= 1_000_000;
  useEffect(() => {
    const abort = new AbortController();
    if (pdf || image || plain)
      fileUrl(file)
        .then(async (value) => {
          if (plain) {
            const response = await fetch(value, { signal: abort.signal });
            if (!response.ok) throw Error("Unable to read this file.");
            const text = await response.text();
            if (!abort.signal.aborted) setContent(text);
          } else if (!abort.signal.aborted) setUrl(value);
        })
        .catch((e) => {
          if (!abort.signal.aborted)
            setError(e instanceof Error ? e.message : "Preview failed.");
        });
    return () => abort.abort();
  }, [file.id]);
  return (
    <Dialog className="file-preview-dialog" title={file.name} onClose={onClose}>
      {error ? (
        <ErrorBox message={error} />
      ) : pdf || image ? (
        url ? (
          pdf ? (
            <iframe
              title={`Preview of ${file.name}`}
              className="pdf-preview"
              src={url}
              referrerPolicy="no-referrer"
            />
          ) : (
            <img className="file-image" src={url} alt={file.name} />
          )
        ) : (
          <Loading />
        )
      ) : plain ? (
        content === null ? (
          <Loading />
        ) : (
          <pre
            className="file-text"
            tabIndex={0}
            role="region"
            aria-label={file.name}
          >
            {content}
          </pre>
        )
      ) : (
        <p className="modal-intro">
          Preview is unavailable for this file type or size. Download it to open
          it on your device.
        </p>
      )}
      <div className="actions form-actions">
        <Button
          icon="download"
          onClick={() =>
            downloadWorkspaceFile(file).catch((e) => notify(e.message, true))
          }
        >
          Download file
        </Button>
        <Button onClick={onClose}>Close preview</Button>
      </div>
    </Dialog>
  );
}
