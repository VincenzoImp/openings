import type { Application } from "../api";
import {
  Banner,
  Button,
  EmptyState,
  ErrorBanner,
  Loading,
  Tabs,
} from "../design";
import { useResource, useUrlState } from "../state";
import { Answers } from "./review/Answers";
import { Details } from "./review/Details";
import { DocumentPanes, useCurrentDocuments } from "./review/DocumentPanes";
import { Head } from "./review/Head";
import { Inputs } from "./review/Inputs";
import { beforeYouSend, tabOf } from "./review/model";
import { Requirements } from "./review/Requirements";
import { Revisions } from "./review/Revisions";
import { Timeline } from "./review/Timeline";

const capital = (text: string) => text[0].toUpperCase() + text.slice(1);

/** The page of one application, once its record is read. */
function Review({
  application,
  reload,
}: {
  application: Application;
  reload: () => void;
}) {
  const [raw, setTab] = useUrlState("tab", "answers");
  const [pane, setPane] = useUrlState("pane", "cv");
  const tab = tabOf(raw);
  const current = useCurrentDocuments(application.id);
  const notices = beforeYouSend(application);
  const open = (next: string) => {
    setTab(next);
    document.getElementById("more")?.scrollIntoView({ block: "start" });
  };
  const key = `${application.id}-${application.version}`;
  return (
    <>
      <Head application={application} pdfs={current.pdfs} reload={reload} />
      {notices.length > 0 && (
        <Banner
          tone="info"
          className="block"
          action={
            <span className="row">
              {notices.map((notice) => (
                <Button
                  key={notice.tab}
                  size="sm"
                  onClick={() => open(notice.tab)}
                >
                  {notice.tab === "answers" ? "Answers" : "Requirements"}
                </Button>
              ))}
            </span>
          }
        >
          <strong>Before you send:</strong>{" "}
          {capital(notices.map((notice) => notice.text).join("; ")).replace(
            /\.?$/,
            ".",
          )}
        </Banner>
      )}
      <DocumentPanes
        application={application}
        current={current}
        shown={pane}
        onShow={setPane}
      />
      <section
        id="more"
        className="card review-more"
        aria-label="Application details"
      >
        <Tabs
          id="review"
          label="Application details"
          value={tab}
          onChange={setTab}
          items={[
            { id: "answers", label: "Answers" },
            {
              id: "requirements",
              label: "Requirements",
              count: application.open_requirements || undefined,
            },
            { id: "timeline", label: "Timeline" },
            { id: "inputs", label: "Inputs" },
            { id: "documents", label: "Documents" },
            { id: "details", label: "Details" },
          ]}
        >
          <div className="body">
            {tab === "requirements" ? (
              <Requirements key={key} application={application} />
            ) : tab === "timeline" ? (
              <Timeline application={application} reload={reload} />
            ) : tab === "inputs" ? (
              <Inputs application={application} />
            ) : tab === "documents" ? (
              <Revisions application={application} />
            ) : tab === "details" ? (
              <Details
                key={key}
                application={application}
                onDeleted={() => (location.hash = "#applications")}
              />
            ) : (
              <Answers application={application} />
            )}
          </div>
        </Tabs>
      </section>
    </>
  );
}

/**
 * Review and apply: the posting, the CV and the letter side by side with the
 * actions that end the task, then answers, requirements, timeline, inputs,
 * documents and details. `#review?application=…&tab=…` opens it.
 */
export default function ReviewPage() {
  const [id] = useUrlState("application", "");
  const record = useResource<Application | null>(
    id ? `/applications/${id}` : null,
    null,
  );
  if (!id)
    return (
      <>
        <h1>Application review</h1>
        <EmptyState
          title="No application is open"
          action={
            <a className="btn" href="#applications">
              Open Applications
            </a>
          }
        >
          Choose an application to review it.
        </EmptyState>
      </>
    );
  if (record.error)
    return (
      <div className="stack">
        <h1>Application</h1>
        <ErrorBanner message={record.error} retry={record.reload} />
        <a className="btn" href="#applications">
          Back to Applications
        </a>
      </div>
    );
  if (record.loading || !record.data)
    return <Loading label="Loading the application…" />;
  return <Review application={record.data} reload={record.reload} />;
}
