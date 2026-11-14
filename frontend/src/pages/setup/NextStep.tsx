import { EmptyState } from "../../design";
import { plural } from "../../library/common";

/** How every day works once the record is complete. */
export function NextStep({ applications }: { applications: number }) {
  return (
    <section className="card" aria-labelledby="next-title">
      <header>
        <h2 id="next-title" className="grow">
          First applications
        </h2>
      </header>
      <div className="body stack">
        <p>When the record is complete, this is how every day works:</p>
        <ol className="next-list">
          <li>
            <strong>Collection finds jobs</strong> on the schedule of your
            searches. Nothing is dismissed automatically; Jobs can hide the ones
            requiring a language you do not speak.
          </li>
          <li>
            <strong>You shortlist the ones you want</strong>; shortlisting
            starts the application. You or your agent add its CV and letter as
            PDFs.
          </li>
          <li>
            <strong>You read what is ready</strong>, with the posting beside the
            documents, send the application yourself and mark it applied.
          </li>
          <li>
            <strong>You record the employer's reply.</strong> After a few weeks
            Stats shows how often employers reply.
          </li>
        </ol>
        {applications ? (
          <p>
            Your workspace has {plural(applications, "application")}; Today
            shows the ones ready for you.
          </p>
        ) : (
          <EmptyState title="No application yet">
            The first ones usually appear within a day of the first search.
          </EmptyState>
        )}
        <div className="row">
          <a className="btn primary" href="#today">
            Go to Today
          </a>
          <a className="btn quiet" href="#jobs">
            Add a job by its address
          </a>
        </div>
      </div>
    </section>
  );
}
