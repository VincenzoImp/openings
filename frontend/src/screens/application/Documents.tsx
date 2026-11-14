// The CV and the letter of an application: the current revision of each, its
// PDF or readable text, the upload of a new one (PDF, optional .tex), and
// its earlier revisions and changes.
import { useRef, useState, type DragEvent, type ReactNode } from "react";
import { Download, FileText, MoreHorizontal, Upload } from "lucide-react";
import { download, save, type Schema } from "../../api/client";
import { Button, IconButton } from "../../ui/Button";
import { ConfirmDialog, Dialog } from "../../ui/Dialog";
import { Icon } from "../../ui/Icon";
import { Menu, type MenuEntry } from "../../ui/Menu";
import { Skeleton } from "../../ui/Page";
import { Segmented } from "../../ui/Tabs";
import { useToast } from "../../ui/Toast";
import { cx } from "../../ui/cx";
import {
  useComparison,
  useDeleteRevision,
  useRevision,
  useRevisions,
  useUpload,
  type Revision,
} from "../applications/data";
import { errorText } from "../applications/dialogs";
import { currentOf, shortDay } from "../applications/model";

export type Kind = "cv" | "letter";
export const KIND_LABEL: Record<Kind, string> = { cv: "CV", letter: "Letter" };
type File_ = Schema<"WorkspaceFile">;

const isPdf = (file: File_) =>
  file.media_type === "application/pdf" || /\.pdf$/i.test(file.name);
const isTex = (file: File_) => /\.(tex|ltx)$/i.test(file.name);
export const pdfOf = (revision?: Revision | null) =>
  revision?.files?.find(isPdf) ?? null;

/** Whether this browser shows PDFs itself; otherwise the text comes first. */
export const canShowPdf = () =>
  typeof navigator === "undefined" || navigator.pdfViewerEnabled !== false;

/** The current CV and letter of an application, each with files and text. */
export function useCurrentDocuments(applicationId: string) {
  const list = useRevisions(applicationId);
  const items = list.data?.items ?? [];
  const cvId = currentOf(items, "cv")?.id;
  const letterId = currentOf(items, "letter")?.id;
  const cv = useRevision(cvId);
  const letter = useRevision(letterId);
  return {
    loading:
      list.isLoading ||
      (!!cvId && cv.isLoading) ||
      (!!letterId && letter.isLoading),
    revisions: items,
    cv: cvId ? (cv.data ?? null) : null,
    letter: letterId ? (letter.data ?? null) : null,
  };
}
export type Current = ReturnType<typeof useCurrentDocuments>;

/** Download a revision's file with the session, under its own name. */
export async function downloadFile(file: File_, name?: string) {
  const result = await download(`${file.url}?inline=false`);
  save(result.blob, name || result.filename || file.name);
}

/**
 * A PDF on a darker well, in the browser's own viewer. Without one (or when
 * it cannot render the file) the well says so and offers the download.
 */
export function PdfView({ file, title }: { file: File_; title: string }) {
  return (
    <div className="ap-well">
      <object
        className="ap-pdf"
        data={`${file.url}#toolbar=0&view=FitH`}
        type="application/pdf"
        aria-label={title}
      >
        <PreviewMissing file={file} />
      </object>
    </div>
  );
}

function PreviewMissing({ file }: { file: File_ }) {
  return (
    <p className="ap-pdf-missing">
      Preview not available ·{" "}
      <button
        type="button"
        className="ap-link"
        onClick={() => void downloadFile(file)}
      >
        Download
      </button>
    </p>
  );
}

/** A revision's readable text, as paper. */
export function TextView({
  revision,
  label,
}: {
  revision: Revision;
  label: string;
}) {
  return (
    <div
      className="ap-well"
      data-text=""
      tabIndex={0}
      role="group"
      aria-label={label}
    >
      {revision.text ? (
        <div className="ap-paper">{revision.text}</div>
      ) : (
        <p className="ap-pdf-missing">No readable text in this version.</p>
      )}
    </div>
  );
}

/** PDF or Text of one revision, with the toggle when both exist. */
export function RevisionView({
  revision,
  kind,
  initial,
}: {
  revision: Revision;
  kind: Kind;
  initial?: "pdf" | "text";
}) {
  const pdf = pdfOf(revision);
  const [view, setView] = useState<"pdf" | "text">(
    initial ?? (canShowPdf() || !revision.text ? "pdf" : "text"),
  );
  const shown = !pdf ? "text" : !revision.text ? "pdf" : view;
  const name = KIND_LABEL[kind];
  return (
    <div className="ap-revision-view">
      {pdf && revision.text && (
        <Segmented
          label={`Show the ${name} as`}
          className="ap-view-toggle"
          value={view}
          onChange={setView}
          options={[
            { value: "pdf", label: "PDF" },
            { value: "text", label: "Text" },
          ]}
        />
      )}
      {shown === "pdf" && pdf ? (
        <PdfView file={pdf} title={`${name} PDF`} />
      ) : (
        <TextView revision={revision} label={`Text of the ${name}`} />
      )}
    </div>
  );
}

/** Pick the PDF and the optional .tex among dropped or chosen files. */
function pickFiles(files: FileList | File[]) {
  const list = [...files];
  return {
    pdf: list.find((file) => /\.pdf$/i.test(file.name)) ?? null,
    source: list.find((file) => /\.(tex|ltx)$/i.test(file.name)) ?? null,
  };
}

/** The upload of a CV or letter, by file picker or drop. */
export function useDocumentUpload(
  applicationId: string,
  kind: Kind,
  previous: Revision | null,
) {
  const upload = useUpload();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const send = (files: FileList | File[]) => {
    const { pdf, source } = pickFiles(files);
    if (!pdf) {
      toast.show({
        message: "Choose a PDF; a .tex source may come with it.",
        tone: "error",
      });
      return;
    }
    // The promise, not the mutate callbacks: the last upload makes the
    // application Ready, and this part of the page gives way to Ready.
    upload.mutateAsync({ applicationId, kind, pdf, source, previous }).then(
      () =>
        toast.show({
          message: `Uploaded the ${KIND_LABEL[kind]}`,
          tone: "success",
        }),
      (error) => toast.show({ message: errorText(error), tone: "error" }),
    );
  };
  const picker = (
    <input
      ref={input}
      type="file"
      hidden
      multiple
      accept=".pdf,application/pdf,.tex,.ltx"
      aria-label={`Upload PDF of the ${KIND_LABEL[kind]}`}
      onChange={(event) => {
        if (event.target.files?.length) send(event.target.files);
        event.target.value = "";
      }}
    />
  );
  return {
    open: () => input.current?.click(),
    send,
    picker,
    busy: upload.isPending,
  };
}

/** A drop target around its children; outlined only while a file is over it. */
function DropZone({
  onFiles,
  className,
  children,
}: {
  onFiles: (files: FileList) => void;
  className?: string;
  children: ReactNode;
}) {
  const [over, setOver] = useState(false);
  const stop = (event: DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
  };
  return (
    <div
      className={className}
      data-over={over || undefined}
      onDragOver={(event) => {
        stop(event);
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        stop(event);
        setOver(false);
        if (event.dataTransfer.files.length) onFiles(event.dataTransfer.files);
      }}
    >
      {children}
    </div>
  );
}

/**
 * The row of a required CV or letter, the same height empty or filled, so
 * an upload never moves the page. Empty: what is missing, and Upload PDF
 * (unless the page's primary already is that upload), by button or drop.
 * Filled: its version, Preview and `…` (Replace, Download, Earlier versions,
 * Show changes, Remove).
 */
export function DocumentSlot({
  kind,
  revision,
  revisions,
  loading,
  uploader,
  primary = false,
}: {
  kind: Kind;
  revision: Revision | null;
  revisions: Revision[];
  loading: boolean;
  uploader: ReturnType<typeof useDocumentUpload>;
  /** The page's primary action uploads this one: no second button here. */
  primary?: boolean;
}) {
  const name = KIND_LABEL[kind];
  const pdf = pdfOf(revision);
  const source = revision?.files?.find(isTex);
  const [dialog, setDialog] = useState<
    "preview" | "versions" | "changes" | "remove" | null
  >(null);
  const remove = useDeleteRevision();
  const toast = useToast();
  const history = revisions.filter((item) => item.kind === kind);
  const menu: MenuEntry[] = revision
    ? [
        { id: "replace", label: "Replace…", onSelect: uploader.open },
        ...(pdf
          ? [
              {
                id: "download",
                label: "Download",
                onSelect: () => void downloadFile(pdf),
              },
            ]
          : []),
        ...(history.length > 1
          ? [
              {
                id: "versions",
                label: "Earlier versions",
                onSelect: () => setDialog("versions"),
              },
            ]
          : []),
        ...(revision.previous_id
          ? [
              {
                id: "changes",
                label: "Show changes from previous version",
                onSelect: () => setDialog("changes"),
              },
            ]
          : []),
        "separator",
        {
          id: "remove",
          label: "Remove…",
          danger: true,
          onSelect: () => setDialog("remove"),
        },
      ]
    : [];
  const missing = !loading && (!revision || !pdf);
  return (
    <DropZone
      className={cx(
        "ap-slot",
        missing && "ap-drop",
        uploader.busy && "is-busy",
      )}
      onFiles={uploader.send}
    >
      <section
        className="ap-slot-row"
        aria-label={name}
        data-empty={missing || undefined}
      >
        <Icon icon={missing ? Upload : FileText} className="ap-slot-icon" />
        <div className="ap-slot-text">
          <h3>{name}</h3>
          {loading ? (
            <Skeleton width={160} height={10} />
          ) : missing ? (
            <p className="ap-slot-meta">
              {revision ? "No PDF yet. " : "Not uploaded yet. "}
              <span className="ap-hint-drop">
                Drop the PDF here, with its .tex source if you have one.
              </span>
              <span className="ap-hint-touch">
                Choose a PDF, with its .tex source if you have one.
              </span>
            </p>
          ) : (
            <p className="ap-slot-meta">
              {`Version ${revision!.revision_number || 1} · ${shortDay(revision!.created_at)}`}
              {source ? ` · with ${source.name}` : ""}
            </p>
          )}
        </div>
        {missing && !primary && (
          <Button
            size="sm"
            icon={Upload}
            disabled={uploader.busy}
            onClick={uploader.open}
          >
            {uploader.busy ? "Uploading…" : "Upload PDF"}
            <span className="ui-sr"> of the {name}</span>
          </Button>
        )}
        {missing && primary && uploader.busy && (
          <span className="ap-slot-meta">Uploading…</span>
        )}
        {!missing && revision && (
          <>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setDialog("preview")}
            >
              Preview
              <span className="ui-sr"> the {name}</span>
            </Button>
            <Menu
              label={`${name} actions`}
              placement="bottom-end"
              items={menu}
              trigger={(props) => (
                <IconButton
                  {...props}
                  icon={MoreHorizontal}
                  label={`${name} actions`}
                  size="sm"
                />
              )}
            />
          </>
        )}
        {revision && missing && (
          <Menu
            label={`${name} actions`}
            placement="bottom-end"
            items={menu}
            trigger={(props) => (
              <IconButton
                {...props}
                icon={MoreHorizontal}
                label={`${name} actions`}
                size="sm"
              />
            )}
          />
        )}
      </section>
      {uploader.picker}
      <Dialog
        open={dialog === "preview" && !!revision}
        onClose={() => setDialog(null)}
        title={name}
        className="ap-preview-dialog"
        footer={
          <Button variant="ghost" onClick={() => setDialog(null)}>
            Close
          </Button>
        }
      >
        {revision && <RevisionView revision={revision} kind={kind} />}
      </Dialog>
      <VersionsDialog
        open={dialog === "versions"}
        onClose={() => setDialog(null)}
        name={name}
        history={history}
        currentId={revision?.id}
      />
      <ChangesDialog
        id={dialog === "changes" ? (revision?.id ?? null) : null}
        name={name}
        onClose={() => setDialog(null)}
      />
      <ConfirmDialog
        open={dialog === "remove"}
        title={`Remove this ${name.toLowerCase()} version?`}
        confirm="Remove permanently"
        onClose={() => setDialog(null)}
        onConfirm={() =>
          revision &&
          remove.mutate(
            { id: revision.id, version: revision.version },
            {
              onSuccess: () =>
                toast.show({
                  message: `Removed ${name} version ${revision.revision_number || 1}`,
                  tone: "success",
                }),
              onError: (error) =>
                toast.show({ message: errorText(error), tone: "error" }),
            },
          )
        }
      >
        {`Version ${revision?.revision_number || 1} and its files are deleted; earlier versions stay. This cannot be undone.`}
      </ConfirmDialog>
    </DropZone>
  );
}

/** Every version of a document, newest first, each downloadable. */
function VersionsDialog({
  open,
  onClose,
  name,
  history,
  currentId,
}: {
  open: boolean;
  onClose: () => void;
  name: string;
  history: Revision[];
  currentId?: string;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Versions of the ${name.toLowerCase()}`}
      footer={
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      }
    >
      <ul className="ap-versions">
        {history.map((item) => (
          <VersionItem
            key={item.id}
            id={item.id}
            current={item.id === currentId}
          />
        ))}
      </ul>
    </Dialog>
  );
}

function VersionItem({ id, current }: { id: string; current: boolean }) {
  const revision = useRevision(id).data;
  const pdf = pdfOf(revision);
  if (!revision) return null;
  return (
    <li>
      <span>
        Version {revision.revision_number || 1}
        <span className="ap-muted">
          {" · "}
          {shortDay(revision.created_at)}
          {current ? " · current" : ""}
          {!pdf ? " · no PDF" : ""}
        </span>
      </span>
      {pdf && (
        <Button
          size="sm"
          variant="ghost"
          icon={Download}
          onClick={() => void downloadFile(pdf)}
        >
          Download
          <span className="ui-sr">
            {" "}
            version {revision.revision_number || 1}
          </span>
        </Button>
      )}
    </li>
  );
}

/** The lines a revision changed from the one it replaced. */
function ChangesDialog({
  id,
  name,
  onClose,
}: {
  id: string | null;
  name: string;
  onClose: () => void;
}) {
  const comparison = useComparison(id);
  const data = comparison.data;
  return (
    <Dialog
      open={!!id}
      onClose={onClose}
      title={`Changes in the ${name.toLowerCase()}`}
      className="ap-wide"
      footer={
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      }
    >
      {!data ? (
        <Skeleton width="80%" />
      ) : (
        <>
          <p className="ap-caption">
            {data.added} added · {data.removed} removed
          </p>
          <ol className="ap-diff" aria-label="Changed lines">
            {data.lines
              .filter((line) => line.change !== "same")
              .map((line, index) => (
                <li key={index} data-change={String(line.change)}>
                  <span aria-hidden="true">
                    {line.change === "added" ? "+" : "−"}
                  </span>
                  <span className="ui-sr">
                    {line.change === "added" ? "Added: " : "Removed: "}
                  </span>
                  {String(line.text)}
                </li>
              ))}
          </ol>
        </>
      )}
    </Dialog>
  );
}

/** The CV and letter that were sent: two downloads, a preview on click. */
export function SentDocuments({ current }: { current: Current }) {
  const [shown, setShown] = useState<Kind | null>(null);
  const docs = (["cv", "letter"] as Kind[])
    .map((kind) => ({ kind, revision: current[kind] }))
    .filter((item) => item.revision && pdfOf(item.revision));
  if (!docs.length) return null;
  const open = docs.find((item) => item.kind === shown);
  return (
    <section className="ap-section" aria-labelledby="ap-sent-title">
      <h2 className="ap-section-title" id="ap-sent-title">
        Sent documents
      </h2>
      <ul className="ap-sent">
        {docs.map(({ kind, revision }) => (
          <li key={kind}>
            <Icon icon={FileText} />
            <button
              type="button"
              className="ap-link"
              onClick={() => setShown(kind)}
            >
              {KIND_LABEL[kind]}
            </button>
            <span className="ap-muted">{pdfOf(revision)!.name}</span>
            <IconButton
              icon={Download}
              size="sm"
              label={`Download the ${KIND_LABEL[kind]}`}
              onClick={() => void downloadFile(pdfOf(revision)!)}
            />
          </li>
        ))}
      </ul>
      <Dialog
        open={!!open}
        onClose={() => setShown(null)}
        title={open ? KIND_LABEL[open.kind] : ""}
        className="ap-preview-dialog"
        footer={
          <Button variant="ghost" onClick={() => setShown(null)}>
            Close
          </Button>
        }
      >
        {open?.revision && (
          <RevisionView revision={open.revision} kind={open.kind} />
        )}
      </Dialog>
    </section>
  );
}
