import { useEffect, useState } from "react";

import { api } from "../../api/client";
import type { Attachment } from "../../api/types";
import { MarkdownBody } from "../../components/MarkdownBody";
import { Spinner } from "../../components/EmptyState";

type Preview =
  | { kind: "loading" }
  | { kind: "pdf" | "image"; url: string }
  | { kind: "markdown" | "text"; text: string }
  | { kind: "none" }
  | { kind: "error"; message: string };

function classifyPreview(
  filename: string,
  type: string,
): "pdf" | "image" | "markdown" | "text" | "none" {
  const lower = filename.toLowerCase();
  if (type === "application/pdf" || lower.endsWith(".pdf")) {
    return "pdf";
  }
  if (type.startsWith("image/")) {
    return "image";
  }
  if (lower.endsWith(".md") || lower.endsWith(".markdown")) {
    return "markdown";
  }
  if (type.startsWith("text/") || /\.(txt|csv|json|yaml|yml|tex)$/.test(lower)) {
    return "text";
  }
  return "none";
}

/**
 * Inline preview fetched with the API token, so it works behind a token gate.
 * Mount with `key={attachment.id}` so a new file starts from the loading state.
 */
export function AttachmentPreview({
  jobId,
  attachment,
}: {
  jobId: string;
  attachment: Attachment;
}) {
  const [state, setState] = useState<Preview>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    api
      .fetchAttachmentBlob(jobId, attachment.id)
      .then(async (blob) => {
        if (cancelled) {
          return;
        }
        const kind = classifyPreview(attachment.filename, blob.type);
        if (kind === "pdf" || kind === "image") {
          objectUrl = URL.createObjectURL(blob);
          setState({ kind, url: objectUrl });
        } else if (kind === "markdown" || kind === "text") {
          setState({ kind, text: await blob.text() });
        } else {
          setState({ kind: "none" });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : String(error),
          });
        }
      });
    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [jobId, attachment.id, attachment.filename]);

  switch (state.kind) {
    case "loading":
      return <Spinner label="Loading preview…" />;
    case "pdf":
      return (
        <object
          data={state.url}
          type="application/pdf"
          className="h-[70dvh] w-full rounded border border-edge"
          aria-label={attachment.filename}
        >
          <p className="p-3 text-sm text-fg-muted">
            This browser does not display PDFs inline. Download the file instead.
          </p>
        </object>
      );
    case "image":
      return (
        <img
          src={state.url}
          alt={attachment.filename}
          className="max-h-[70dvh] w-auto max-w-full rounded border border-edge"
        />
      );
    case "markdown":
      return <MarkdownBody text={state.text} className="rounded border border-edge p-3" />;
    case "text":
      return (
        <pre
          tabIndex={0}
          className="max-h-[70dvh] overflow-auto whitespace-pre-wrap rounded border border-edge bg-surface-2 p-3 text-xs text-fg"
        >
          {state.text}
        </pre>
      );
    case "none":
      return (
        <p className="text-sm text-fg-muted">
          No inline preview for this file type. Download it to open.
        </p>
      );
    case "error":
      return <p className="text-sm text-negative">{state.message}</p>;
  }
}
