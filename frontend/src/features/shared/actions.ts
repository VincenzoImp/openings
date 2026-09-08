import { useCallback } from "react";

import type { JobSummary } from "../../api/types";
import { useConfirm } from "../../app/confirmContext";
import { navigate } from "../../app/router";
import { useJobCommands } from "./queries";

/** The actions every list and the job page share, with their confirmations. */
export function useJobActions() {
  const commands = useJobCommands();
  const confirm = useConfirm();

  const open = useCallback(
    (job: Pick<JobSummary, "job_id">) => navigate({ jobId: job.job_id }),
    [],
  );
  const openPosting = useCallback((job: Pick<JobSummary, "job_url">) => {
    if (job.job_url) {
      window.open(job.job_url, "_blank", "noopener");
    }
  }, []);

  const blacklist = useCallback(
    async (jobs: Pick<JobSummary, "job_id" | "title" | "company">[]) => {
      if (jobs.length === 0) {
        return false;
      }
      const message =
        jobs.length === 1
          ? `“${jobs[0].title}” at ${jobs[0].company} disappears from every list and is never ingested again. Notes and files are kept; you can restore it from System › Blacklist.`
          : `${jobs.length} jobs disappear from every list and are never ingested again. Notes and files are kept; you can restore them from System › Blacklist.`;
      const ok = await confirm({
        title: jobs.length === 1 ? "Blacklist this posting?" : `Blacklist ${jobs.length} postings?`,
        message,
        confirmLabel: "Blacklist",
        danger: true,
      });
      if (ok) {
        commands.blacklist.mutate({ jobIds: jobs.map((job) => job.job_id) });
      }
      return ok;
    },
    [commands.blacklist, confirm],
  );

  const remove = useCallback(
    async (jobs: Pick<JobSummary, "job_id" | "title">[]) => {
      if (jobs.length === 0) {
        return false;
      }
      const ok = await confirm({
        title: jobs.length === 1 ? "Delete this job?" : `Delete ${jobs.length} jobs?`,
        message:
          "The job, its notes and attachments are deleted. A later run can ingest the posting again.",
        confirmLabel: "Delete",
        danger: true,
      });
      if (ok) {
        commands.deleteJobs.mutate(jobs.map((job) => job.job_id));
      }
      return ok;
    },
    [commands.deleteJobs, confirm],
  );

  return { ...commands, open, openPosting, blacklist, remove };
}
