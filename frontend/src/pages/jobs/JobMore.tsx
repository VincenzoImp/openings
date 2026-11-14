import { useState } from "react";
import { api, date, type Job } from "../../api";
import { Button, Tag } from "../../design";
import { Assets } from "../../library/Assets";
import { ConfirmDialog } from "../../library/common";
import { dayTime } from "../../library/time";
import { useWorkspace } from "../../state";
import type { Links } from "../../library/records";
import { EditJob } from "./EditJob";
import { MergeDialog } from "./MergeDialog";

const KINDS: Record<string, string> = { jobspy: "Search", rss: "Feed" };

/** Where the job was seen: each source, when, and whether it still lists the posting. */
function Sources({ job }: { job: Job }) {
  if (!job.postings?.length)
    return <p className="muted">Added by hand: no source has seen it.</p>;
  return (
    <ul className="list compact" aria-label="Sources that saw this job">
      {job.postings.map((posting) => (
        <li key={posting.id}>
          <div className="grow">
            <div className="title">
              {posting.source_name ||
                (posting.source_id ? "A removed source" : "Added by address")}
              {posting.source_kind && (
                <span className="muted">
                  {" "}
                  · {KINDS[posting.source_kind] || "Company board"}
                </span>
              )}
            </div>
            <div className="meta">
              First seen {date(posting.first_seen_at)} · last seen{" "}
              {dayTime(posting.last_seen_at).toLowerCase()}
            </div>
            {posting.url && (
              <a
                className="meta"
                href={posting.url}
                target="_blank"
                rel="noreferrer"
              >
                {posting.url}
              </a>
            )}
          </div>
          {posting.unlisted_at && (
            <Tag tone="danger">
              No longer listed since {date(posting.unlisted_at)}
            </Tag>
          )}
        </li>
      ))}
    </ul>
  );
}

/**
 * What is kept with the job and changed less often: its details, the sources
 * that saw it, a merge with another job, files, and forgetting it for good.
 */
export function JobMore({
  job,
  onGone,
  onOpenJob,
}: Links & { job: Job; onGone: () => void }) {
  const { mutate } = useWorkspace();
  const [forgetting, setForgetting] = useState(false);
  const [merging, setMerging] = useState(false);
  return (
    <section className="detail-section more" aria-labelledby="more-title">
      <h3 id="more-title">Details</h3>
      <details>
        <summary>Correct the job</summary>
        <EditJob key={`${job.id}-${job.version}`} job={job} />
      </details>
      <details>
        <summary>Sources ({job.postings?.length || 0})</summary>
        <Sources job={job} />
      </details>
      <details>
        <summary>Files</summary>
        <div className="card">
          <Assets
            ownerType="job"
            ownerId={job.id}
            empty="No file is kept with this job."
            note="Screenshots or a saved copy of the posting."
          />
        </div>
      </details>
      <div className="row">
        <Button size="sm" variant="quiet" onClick={() => setMerging(true)}>
          Merge with another job…
        </Button>
        <Button
          size="sm"
          variant="quiet danger"
          onClick={() => setForgetting(true)}
        >
          Forget this job permanently
        </Button>
      </div>
      {merging && (
        <MergeDialog
          job={job}
          target={null}
          onClose={() => setMerging(false)}
          onMerged={(kept) => {
            setMerging(false);
            onOpenJob(kept);
          }}
        />
      )}
      {forgetting && (
        <ConfirmDialog
          title="Forget this job?"
          confirm="Forget the job"
          keep="Keep the job"
          onClose={() => setForgetting(false)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/jobs/${job.id}?expected_version=${job.version}`,
                    "DELETE",
                  ),
                "Job and its records removed.",
              )
            ) {
              setForgetting(false);
              onGone();
            }
          }}
        >
          <p>
            The job is removed for good with its applications, notes and files.
            If a source collects it again, it is a new job. To stop seeing it
            and keep its history, dismiss it instead.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
