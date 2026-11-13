import type { Job } from "../../api";
import { RecordTimeline } from "../../library/Timeline";

/** Everything recorded about the job and its applications, with its notes and a form to add one. */
export function JobTimeline({ job }: { job: Job }) {
  return (
    <section className="detail-section" aria-labelledby="timeline-title">
      <h3 id="timeline-title">Timeline</h3>
      <RecordTimeline jobId={job.id} label="Timeline of this job" />
    </section>
  );
}
