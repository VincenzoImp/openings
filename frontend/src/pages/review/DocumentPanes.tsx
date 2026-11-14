import { useEffect, useState } from "react";
import {
  fileUrl,
  type Application,
  type Document,
  type ListResult,
  type WorkspaceFile,
} from "../../api";
import {
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Loading,
  Panes,
  SegmentedControl,
  Tag,
} from "../../design";
import { FileDialog } from "../../library/Assets";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { currentOf, isPdf, isSource, kindLabels } from "./model";
import { RevisionDialog } from "./RevisionDialog";

const NONE: ListResult<Document> = { items: [], total: 0 };

const SCOPES = ["documents", "files"];

/** The current CV and letter of an application, with their files. */
export function useCurrentDocuments(applicationId: string) {
  // Read again after every document or file change, whatever form is open.
  const list = useFresh<ListResult<Document>>(
    `/documents?application_id=${applicationId}&summary=true&limit=100`,
    NONE,
    SCOPES,
  );
  const cvId = currentOf(list.data.items, "cv")?.id;
  const letterId = currentOf(list.data.items, "letter")?.id;
  const cv = useFresh<Document | null>(
    cvId ? `/documents/${cvId}` : null,
    null,
    SCOPES,
  );
  const letter = useFresh<Document | null>(
    letterId ? `/documents/${letterId}` : null,
    null,
    SCOPES,
  );
  const pdfs = [cv.data, letter.data]
    .map((item) => item?.files?.find(isPdf))
    .filter((file): file is WorkspaceFile => Boolean(file));
  return { list, cv, letter, pdfs };
}
type Current = ReturnType<typeof useCurrentDocuments>;

/** The PDF of a revision in the browser's own viewer. */
function PdfFrame({ file, title }: { file: WorkspaceFile; title: string }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setUrl("");
    fileUrl(file)
      .then((value) => {
        if (active)
          setUrl(`${value}${value.includes("?") ? "&" : "?"}inline=true`);
      })
      .catch((cause) => active && setError(String(cause)));
    return () => {
      active = false;
    };
  }, [file.id]);
  if (error) return <ErrorBanner message={error} />;
  if (!url) return <Loading label="Loading the PDF…" />;
  return (
    <iframe
      className="frame"
      title={title}
      src={`${url}#toolbar=0&view=FitH`}
      referrerPolicy="no-referrer"
    />
  );
}

/**
 * One current revision: its PDF beside its readable text, one at a time, or
 * the text alone while it has no PDF; and the upload of a new PDF.
 */
function RevisionPane({
  application,
  kind,
  revision,
  loading,
}: {
  application: Application;
  kind: "cv" | "letter";
  revision: Document | null;
  loading: boolean;
}) {
  const [opened, setOpened] = useState<WorkspaceFile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [view, setView] = useState("pdf");
  const name = kindLabels[kind];
  const pdf = revision?.files?.find(isPdf);
  const source = revision?.files?.find(isSource);
  const text = revision?.text || "";
  const shown = pdf && text ? view : pdf ? "pdf" : "text";
  const required = (
    application.required_documents || ["cv", "letter"]
  ).includes(kind);
  return (
    <Card
      title={name}
      actions={
        revision && (
          <>
            <Tag tone={pdf ? "ready" : "attention"}>
              {pdf ? "Complete" : "Without PDF"}
            </Tag>
            {pdf && (
              <button
                type="button"
                className="btn quiet sm"
                onClick={() => setOpened(pdf)}
              >
                PDF<span className="sr"> of the {name}</span>
              </button>
            )}
          </>
        )
      }
    >
      {!loading && pdf && text && (
        <SegmentedControl
          label={`Show the ${name} as`}
          options={[
            { id: "pdf", label: "PDF" },
            { id: "text", label: "Text" },
          ]}
          value={view}
          onChange={setView}
        />
      )}
      <div className="scroll">
        {loading ? (
          <Loading label={`Loading the ${name}…`} />
        ) : !revision ? (
          <EmptyState title={`No ${name} yet`}>
            {required
              ? `Upload the ${name} as a PDF, with its .tex source if you have one. The application is Ready once its required documents are uploaded.`
              : `This application does not require a ${name}.`}
          </EmptyState>
        ) : pdf && shown === "pdf" ? (
          <PdfFrame file={pdf} title={`Preview of the ${name}, ${pdf.name}`} />
        ) : text ? (
          <div
            className="paper"
            role="document"
            aria-label={`Text of the ${name}`}
          >
            {text}
          </div>
        ) : (
          <EmptyState title="No PDF yet">
            This revision has no PDF yet, so it does not count for Ready. Upload
            its PDF.
          </EmptyState>
        )}
      </div>
      <footer>
        <span className="caption">
          {revision && (
            <>
              Revision {revision.revision_number || 1}
              {source && (
                <>
                  {" · built from "}
                  <span className="mono">{source.name}</span>
                </>
              )}
              {" · "}
              {dayTime(revision.created_at)}
              {!pdf && " · no PDF"}
            </>
          )}
        </span>
        <Button size="sm" icon="upload" onClick={() => setUploading(true)}>
          {pdf ? "New PDF" : "Upload PDF"}
          <span className="sr"> of the {name}</span>
        </Button>
      </footer>
      {opened && <FileDialog file={opened} onClose={() => setOpened(null)} />}
      {uploading && (
        <RevisionDialog
          application={application}
          previous={revision || undefined}
          kind={kind}
          onClose={() => setUploading(false)}
        />
      )}
    </Card>
  );
}

function PostingPane({ application }: { application: Application }) {
  const job = application.job;
  return (
    <Card
      title="Posting"
      actions={
        job?.url ? (
          <a
            className="btn quiet sm"
            href={job.url}
            target="_blank"
            rel="noreferrer"
          >
            Open<span aria-hidden="true"> ↗</span>
            <span className="sr"> the posting in a new tab</span>
          </a>
        ) : undefined
      }
    >
      <div className="scroll">
        {job?.posting?.trim() ? (
          <div className="posting">{job.posting}</div>
        ) : (
          <EmptyState title="The posting text is missing">
            Open the job to paste the full posting.
          </EmptyState>
        )}
      </div>
      <footer>
        <span className="caption">
          {job?.source && job.source !== "manual"
            ? `From ${job.source} · `
            : ""}
          Collected {dayTime(job?.created_at)}
        </span>
        {job && (
          <a className="btn quiet sm" href={`#jobs?job=${job.id}`}>
            Job details
          </a>
        )}
      </footer>
    </Card>
  );
}

/**
 * The posting, the CV and the letter side by side; one at a time, chosen
 * with a switch, on a phone.
 */
export function DocumentPanes({
  application,
  current,
  shown,
  onShow,
}: {
  application: Application;
  current: Current;
  shown: string;
  onShow: (pane: string) => void;
}) {
  const { list, cv, letter } = current;
  if (list.error)
    return <ErrorBanner message={list.error} retry={list.reload} />;
  const loading = (part: typeof cv) => list.loading || part.loading;
  return (
    <Panes
      label="Shown document"
      shown={shown}
      onShow={onShow}
      order={["cv", "letter", "posting"]}
      items={[
        {
          id: "posting",
          label: "Posting",
          content: <PostingPane application={application} />,
        },
        {
          id: "cv",
          label: "CV",
          content: (
            <RevisionPane
              application={application}
              kind="cv"
              revision={cv.data}
              loading={loading(cv)}
            />
          ),
        },
        {
          id: "letter",
          label: "Letter",
          content: (
            <RevisionPane
              application={application}
              kind="letter"
              revision={letter.data}
              loading={loading(letter)}
            />
          ),
        },
      ]}
    />
  );
}
