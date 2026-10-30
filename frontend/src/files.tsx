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
import { Button, Dialog, ErrorBox, Field, Icon, Pagination } from "./ui";
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
      <div className="document-files">
        {data.items.map((file) => (
          <div className="documentrow" key={file.id}>
            <Icon name="file" />
            <div className="doccopy">
              <button
                className="table-link"
                onClick={() =>
                  api<WorkspaceFile>(`/files/${file.id}`)
                    .then(setInspecting)
                    .catch((e) => notify(e.message, true))
                }
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
              aria-label={`Download ${file.name}`}
              onClick={() =>
                downloadWorkspaceFile(file).catch((e) =>
                  notify(String(e), true),
                )
              }
            >
              <Icon name="download" />
            </button>
            {!immutable && (
              <button
                className="iconbtn danger"
                aria-label={`Delete ${file.name}`}
                disabled={pending}
                onClick={() =>
                  mutate(
                    () => api(`/files/${file.id}`, "DELETE"),
                    "File removed.",
                  )
                }
              >
                <Icon name="trash" />
              </button>
            )}
          </div>
        ))}
      </div>
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
