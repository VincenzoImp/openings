import { useEffect, useState } from "react";
import {
  api,
  date,
  fileUrl,
  uploadFile,
  type ListResult,
  type WorkspaceFile,
} from "./api";
import { useResource, useWorkspace } from "./state";
import { Button, ErrorBox, Icon } from "./ui";
export function FileManager({
  ownerType,
  ownerId,
  immutable = false,
  preview = false,
}: {
  ownerType: string;
  ownerId: string;
  immutable?: boolean;
  preview?: boolean;
}) {
  const { data, error, reload } = useResource<ListResult<WorkspaceFile>>(
    `/files?owner_type=${ownerType}&owner_id=${ownerId}`,
    { items: [], total: 0 },
  );
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
      <div className="document-files">
        {data.items.map((file) => (
          <div className="documentrow" key={file.id}>
            <Icon name="file" />
            <div className="doccopy">
              <strong>{file.name}</strong>
              <small>
                {Math.max(1, Math.round(file.size / 1024))} KB ·{" "}
                {date(file.created_at)}
              </small>
            </div>
            <button
              className="iconbtn"
              aria-label={`Download ${file.name}`}
              onClick={() =>
                fileUrl(file)
                  .then((url) => window.open(url, "_blank", "noopener"))
                  .catch((e) => notify(String(e), true))
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
