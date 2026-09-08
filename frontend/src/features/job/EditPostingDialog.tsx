import { useState } from "react";

import type { JobDetail, PostingFields } from "../../api/types";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Field, Input, Select, Textarea } from "../../components/Field";
import { useJobCommands } from "../shared/queries";

interface Draft {
  title: string;
  company: string;
  location: string;
  job_url: string;
  description: string;
  date_posted: string;
  job_type: string;
  is_remote: "" | "true" | "false";
  job_level: string;
  min_amount: string;
  max_amount: string;
  currency: string;
  salary_interval: string;
  company_url: string;
}

const NULLABLE = [
  "job_url",
  "description",
  "date_posted",
  "job_type",
  "job_level",
  "currency",
  "salary_interval",
  "company_url",
] as const;

function toDraft(job: JobDetail): Draft {
  return {
    title: job.title,
    company: job.company,
    location: job.location,
    job_url: job.job_url ?? "",
    description: job.description ?? "",
    date_posted: job.date_posted ?? "",
    job_type: job.job_type ?? "",
    is_remote: job.is_remote === null ? "" : job.is_remote ? "true" : "false",
    job_level: job.job_level ?? "",
    min_amount: job.min_amount === null ? "" : String(job.min_amount),
    max_amount: job.max_amount === null ? "" : String(job.max_amount),
    currency: job.currency ?? "",
    salary_interval: job.salary_interval ?? "",
    company_url: job.company_url ?? "",
  };
}

/** Only the fields that changed are sent, so an untouched form is a no-op. */
function diffPosting(job: JobDetail, draft: Draft): PostingFields {
  const base = toDraft(job);
  const out: PostingFields = {};
  for (const key of ["title", "company", "location"] as const) {
    if (draft[key].trim() !== base[key]) {
      out[key] = draft[key].trim();
    }
  }
  for (const key of NULLABLE) {
    if (draft[key] !== base[key]) {
      out[key] = draft[key].trim() || null;
    }
  }
  if (draft.is_remote !== base.is_remote) {
    out.is_remote = draft.is_remote === "" ? null : draft.is_remote === "true";
  }
  if (draft.min_amount !== base.min_amount) {
    out.min_amount = draft.min_amount === "" ? null : Number(draft.min_amount);
  }
  if (draft.max_amount !== base.max_amount) {
    out.max_amount = draft.max_amount === "" ? null : Number(draft.max_amount);
  }
  return out;
}

function EditPostingForm({ job, onClose }: { job: JobDetail; onClose: () => void }) {
  const { updateJob } = useJobCommands();
  const [draft, setDraft] = useState<Draft>(() => toDraft(job));
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const changes = diffPosting(job, draft);
  const dirty = Object.keys(changes).length > 0;
  const valid = draft.title.trim() !== "" && draft.company.trim() !== "";

  const submit = () => {
    if (!dirty || !valid) {
      onClose();
      return;
    }
    updateJob.mutate({ jobId: job.job_id, fields: changes }, { onSuccess: onClose });
  };

  return (
    <form
      className="grid gap-3 sm:grid-cols-2"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <Field label="Title" htmlFor="edit-title">
        <Input
          id="edit-title"
          value={draft.title}
          onChange={(e) => set("title", e.target.value)}
          required
          autoFocus
        />
      </Field>
      <Field label="Company" htmlFor="edit-company">
        <Input
          id="edit-company"
          value={draft.company}
          onChange={(e) => set("company", e.target.value)}
          required
        />
      </Field>
      <Field label="Location" htmlFor="edit-location">
        <Input
          id="edit-location"
          value={draft.location}
          onChange={(e) => set("location", e.target.value)}
        />
      </Field>
      <Field label="Posting URL" htmlFor="edit-url">
        <Input
          id="edit-url"
          type="url"
          inputMode="url"
          value={draft.job_url}
          onChange={(e) => set("job_url", e.target.value)}
        />
      </Field>
      <div className="sm:col-span-2">
        <Field label="Description (markdown)" htmlFor="edit-description">
          <Textarea
            id="edit-description"
            className="min-h-40"
            value={draft.description}
            onChange={(e) => set("description", e.target.value)}
          />
        </Field>
      </div>
      <Field label="Posted on" htmlFor="edit-date">
        <Input
          id="edit-date"
          type="date"
          value={draft.date_posted}
          onChange={(e) => set("date_posted", e.target.value)}
        />
      </Field>
      <Field label="Job type" htmlFor="edit-type">
        <Input
          id="edit-type"
          value={draft.job_type}
          onChange={(e) => set("job_type", e.target.value)}
        />
      </Field>
      <Field label="Level" htmlFor="edit-level">
        <Input
          id="edit-level"
          value={draft.job_level}
          onChange={(e) => set("job_level", e.target.value)}
        />
      </Field>
      <Field label="Remote" htmlFor="edit-remote">
        <Select
          id="edit-remote"
          value={draft.is_remote}
          onChange={(e) => set("is_remote", e.target.value as Draft["is_remote"])}
        >
          <option value="">Unknown</option>
          <option value="true">Remote</option>
          <option value="false">On site</option>
        </Select>
      </Field>
      <Field label="Salary minimum" htmlFor="edit-min">
        <Input
          id="edit-min"
          type="number"
          inputMode="numeric"
          value={draft.min_amount}
          onChange={(e) => set("min_amount", e.target.value)}
        />
      </Field>
      <Field label="Salary maximum" htmlFor="edit-max">
        <Input
          id="edit-max"
          type="number"
          inputMode="numeric"
          value={draft.max_amount}
          onChange={(e) => set("max_amount", e.target.value)}
        />
      </Field>
      <Field label="Currency" htmlFor="edit-currency">
        <Input
          id="edit-currency"
          value={draft.currency}
          onChange={(e) => set("currency", e.target.value)}
        />
      </Field>
      <Field label="Salary interval" htmlFor="edit-interval">
        <Input
          id="edit-interval"
          value={draft.salary_interval}
          onChange={(e) => set("salary_interval", e.target.value)}
          placeholder="yearly, monthly…"
        />
      </Field>
      <div className="sm:col-span-2">
        <Field label="Company URL" htmlFor="edit-company-url">
          <Input
            id="edit-company-url"
            type="url"
            inputMode="url"
            value={draft.company_url}
            onChange={(e) => set("company_url", e.target.value)}
          />
        </Field>
      </div>
      <div className="flex justify-end gap-2 sm:col-span-2">
        <Button onClick={onClose}>Cancel</Button>
        <Button type="submit" variant="primary" disabled={!dirty || !valid || updateJob.isPending}>
          {updateJob.isPending ? "Saving…" : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}

export function EditPostingDialog({
  open,
  job,
  onClose,
}: {
  open: boolean;
  job: JobDetail;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} title="Edit Posting" onClose={onClose} wide>
      <EditPostingForm job={job} onClose={onClose} />
    </Dialog>
  );
}
