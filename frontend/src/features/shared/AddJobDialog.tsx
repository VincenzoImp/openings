import { useState } from "react";

import { JOB_STATUSES } from "../../api/types";
import type { JobStatus } from "../../api/types";
import { navigate } from "../../app/router";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Field, Input, Select, Textarea } from "../../components/Field";
import { STATUS_LABELS } from "./format";
import { useJobCommands } from "./queries";

export function AddJobDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { addJob } = useJobCommands();
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<JobStatus>("shortlisted");
  const [labels, setLabels] = useState("");

  const reset = () => {
    setTitle("");
    setCompany("");
    setLocation("");
    setUrl("");
    setDescription("");
    setStatus("shortlisted");
    setLabels("");
  };

  const submit = () => {
    addJob.mutate(
      {
        title: title.trim(),
        company: company.trim(),
        location: location.trim(),
        job_url: url.trim() || null,
        description: description.trim() || null,
        status,
        labels: labels
          .split(",")
          .map((label) => label.trim())
          .filter(Boolean),
      },
      {
        onSuccess: (result) => {
          reset();
          onClose();
          if (result.job_ids[0]) {
            navigate({ jobId: result.job_ids[0] });
          }
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      title="Add a posting"
      onClose={onClose}
      wide
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            disabled={!title.trim() || !company.trim() || addJob.isPending}
            onClick={submit}
          >
            Add job
          </Button>
        </>
      }
    >
      <form
        className="grid gap-3 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <Field label="Title" htmlFor="add-title">
          <Input id="add-title" value={title} onChange={(e) => setTitle(e.target.value)} required />
        </Field>
        <Field label="Company" htmlFor="add-company">
          <Input
            id="add-company"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            required
          />
        </Field>
        <Field label="Location" htmlFor="add-location">
          <Input id="add-location" value={location} onChange={(e) => setLocation(e.target.value)} />
        </Field>
        <Field label="Posting URL" htmlFor="add-url">
          <Input id="add-url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} />
        </Field>
        <Field label="Status" htmlFor="add-status">
          <Select
            id="add-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as JobStatus)}
          >
            {JOB_STATUSES.map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Labels" htmlFor="add-labels" hint="Comma separated">
          <Input id="add-labels" value={labels} onChange={(e) => setLabels(e.target.value)} />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Description (markdown)" htmlFor="add-description">
            <Textarea
              id="add-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-32"
            />
          </Field>
        </div>
      </form>
    </Dialog>
  );
}
