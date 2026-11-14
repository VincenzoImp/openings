import { ExternalLink, FileSearch, Upload } from "lucide-react";
import { Button } from "../../ui/Button";
import { formatDay } from "../../ui/format";
import { Icon } from "../../ui/Icon";
import { EmptyState, SkeletonRows } from "../../ui/Page";
import { useTemplateFiles, type Template } from "../../query/templates";
import { useFilePicker } from "./Files";
import { isPdf } from "./model";

/** The template's sample PDF, if one was uploaded; the workspace runs no TeX. */
export function PreviewTab({ template }: { template: Template }) {
  const files = useTemplateFiles(template.id);
  const { picker, open, busy } = useFilePicker(
    template,
    ".pdf,application/pdf",
  );
  const pdf = (files.data?.items ?? [])
    .filter(isPdf)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  if (files.isPending) return <SkeletonRows rows={3} />;
  if (!pdf)
    return (
      <>
        {picker}
        <EmptyState
          icon={FileSearch}
          title="No preview"
          actions={
            <Button icon={Upload} onClick={open} disabled={busy}>
              {busy ? "Uploading…" : "Upload a sample PDF"}
            </Button>
          }
        >
          Compile the source on your machine and upload the PDF to see it here.
        </EmptyState>
      </>
    );
  const src = `/api/v1/files/${encodeURIComponent(pdf.id)}/content?inline=true`;
  return (
    <div className="tpl-preview">
      <div className="tpl-bar">
        <span className="tpl-file">{pdf.name}</span>
        <span className="tpl-bar-note">Added {formatDay(pdf.created_at)}</span>
        <span className="tpl-bar-space" />
        <a className="tpl-open" href={src} target="_blank" rel="noreferrer">
          <Icon icon={ExternalLink} size="sm" />
          Open PDF
        </a>
      </div>
      <iframe
        className="tpl-pdf"
        title={`Sample of ${template.name}`}
        src={`${src}#toolbar=0&view=FitH`}
        referrerPolicy="no-referrer"
      />
    </div>
  );
}
