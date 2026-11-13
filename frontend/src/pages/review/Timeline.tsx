import type { Application } from "../../api";
import { RecordTimeline } from "../../library/Timeline";
import { Responses } from "./Responses";

/**
 * The employer's responses, then one timeline of the application: its notes
 * and changes with who made them, and its job's, each marked with its scope.
 */
export function Timeline({
  application,
  reload,
}: {
  application: Application;
  reload: () => void;
}) {
  return (
    <div className="stack">
      <Responses application={application} reload={reload} />
      <section className="stack" aria-labelledby="history-title">
        <h3 id="history-title">Notes and changes</h3>
        <RecordTimeline
          jobId={application.job_id}
          applicationId={application.id}
          label="Timeline of this application"
        />
      </section>
    </div>
  );
}
