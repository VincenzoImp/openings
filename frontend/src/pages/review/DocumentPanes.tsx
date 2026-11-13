import { useEffect, useState } from "react";
import {
  fileUrl,
  type Application,
  type Document,
  type ListResult,
  type WorkspaceFile,
} from "../../api";
import {
  Card,
  EmptyState,
  ErrorBanner,
  Loading,
  Panes,
  Tag,
} from "../../design";
import { FileDialog } from "../../library/Assets";
import { dayTime } from "../../library/time";
import { useResource } from "../../state";
import { currentOf, isPdf, isSource, kindLabels } from "./model";

const NONE: ListResult<Document> = { items: [], total: 0 };

/** The current CV and letter of an application, with their files. */
export function useCurrentDocuments(applicationId: string) {
  const list = useResource<ListResult<Document>>(
    `/documents?application_id=${applicationId}&summary=true&limit=100`,
    NONE,
  );
  const cvId = currentOf(list.data.items, "resume")?.id;
  const letterId = currentOf(list.data.items, "cover_letter")?.id;
  const cv = useResource<Document | null>(
    cvId ? `/documents/${cvId}` : null,
    null,
  );
  const letter = useResource<Document | null>(
    letterId ? `/documents/${letterId}` : null,
    null,
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

/** One current revision: its PDF, or its text when it has none yet. */
function RevisionPane({
  kind,
  revision,
  loading,
}: {
  kind: "resume" | "cover_letter";
  revision: Document | null;
  loading: boolean;
}) {
  const [opened, setOpened] = useState<WorkspaceFile | null>(null);
  const name = kindLabels[kind];
  const pdf = revision?.files?.find(isPdf);
  const source = revision?.files?.find(isSource);
  const text =
    typeof revision?.content?.text === "string" ? revision.content.text : "";
  const approved = revision?.review_state === "approved";
  return (
    <Card
      title={name}
      actions={
        revision && (
          <>
            <Tag tone={approved ? "ready" : "attention"}>
              {approved ? "Approved" : "Not approved"}
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
      <div className="scroll">
        {loading ? (
          <Loading label={`Loading the ${name}…`} />
        ) : !revision ? (
          <EmptyState title={`No ${name} yet`}>
            Your agent writes it from a frozen copy of your record. It appears
            here with its PDF.
          </EmptyState>
        ) : pdf ? (
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
            This revision has no PDF. Its files are in the Documents tab.
          </EmptyState>
        )}
      </div>
      {revision && (
        <footer>
          <span className="caption">
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
          </span>
        </footer>
      )}
      {opened && <FileDialog file={opened} onClose={() => setOpened(null)} />}
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
          <a className="btn quiet sm" href={`#inbox?job=${job.id}`}>
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
              kind="resume"
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
              kind="cover_letter"
              revision={letter.data}
              loading={loading(letter)}
            />
          ),
        },
      ]}
    />
  );
}
